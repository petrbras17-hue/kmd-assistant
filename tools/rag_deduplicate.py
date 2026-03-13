"""
RAG Deduplication Tool for Pinecone kmd-knowledge index.

Finds and removes duplicate vectors within namespaces by:
1. Listing all vector IDs in a namespace (paginated)
2. Fetching vectors in batches to get metadata/values
3. Hashing content to detect identical vectors with different IDs
4. Optionally deleting duplicates (--dry-run by default)

Usage:
    python tools/rag_deduplicate.py --namespace gost-standards --dry-run
    python tools/rag_deduplicate.py --namespace gost-standards --delete
    python tools/rag_deduplicate.py --delete-namespace test
    python tools/rag_deduplicate.py --delete-namespace test --delete
    python tools/rag_deduplicate.py --all --dry-run
    python tools/rag_deduplicate.py --all --delete
"""

import os
import sys
import json
import argparse
import hashlib
from collections import defaultdict
from time import sleep

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_HOST = os.getenv(
    "PINECONE_HOST", "kmd-knowledge-b0hkvr1.svc.aped-4627-b74a.pinecone.io"
)
INDEX_URL = f"https://{PINECONE_HOST}"

NAMESPACES_TO_CHECK = ["gost-standards", "articles-reynaers", "articles-alutech"]

# Rate-limiting delay between API calls (seconds)
RATE_LIMIT_DELAY = 0.5

# Batch size for fetching vectors
FETCH_BATCH_SIZE = 50


def _headers() -> dict[str, str]:
    """Return common headers for Pinecone REST API."""
    return {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }


def list_vector_ids(namespace: str) -> list[str]:
    """List all vector IDs in a namespace using paginated list endpoint.

    Returns a flat list of vector ID strings.
    """
    all_ids: list[str] = []
    pagination_token: str | None = None

    while True:
        params: dict[str, str | int] = {
            "namespace": namespace,
            "limit": 100,
        }
        if pagination_token:
            params["paginationToken"] = pagination_token

        resp = httpx.get(
            f"{INDEX_URL}/vectors/list",
            headers=_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        vectors = data.get("vectors", [])
        for v in vectors:
            all_ids.append(v["id"])

        pagination_token = data.get("pagination", {}).get("next")
        if not pagination_token:
            break

        sleep(RATE_LIMIT_DELAY)

    return all_ids


def fetch_vectors(namespace: str, ids: list[str]) -> dict[str, dict]:
    """Fetch vectors by IDs from a namespace. Returns {id: vector_data}."""
    result: dict[str, dict] = {}

    for i in range(0, len(ids), FETCH_BATCH_SIZE):
        batch = ids[i : i + FETCH_BATCH_SIZE]

        # Build query string with repeated ids params
        params: list[tuple[str, str]] = [("namespace", namespace)]
        for vid in batch:
            params.append(("ids", vid))

        resp = httpx.get(
            f"{INDEX_URL}/vectors/fetch",
            headers=_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        vectors = data.get("vectors", {})
        result.update(vectors)

        if i + FETCH_BATCH_SIZE < len(ids):
            sleep(RATE_LIMIT_DELAY)

    return result


def _content_hash(vector_data: dict) -> str:
    """Create a content hash for a vector to detect duplicates.

    Uses metadata text content if available, falls back to values array.
    """
    # Try metadata content fields first (most reliable for semantic dedup)
    metadata = vector_data.get("metadata", {})

    # Common content fields in our index
    content_parts = []
    for key in ("text", "content", "chunk_text", "title", "source"):
        val = metadata.get(key)
        if val:
            content_parts.append(f"{key}:{val}")

    if content_parts:
        raw = "|".join(content_parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # Fallback: hash the values (embedding vector)
    values = vector_data.get("values", [])
    if values:
        # Round to 6 decimals to handle floating-point noise
        rounded = [round(v, 6) for v in values]
        raw = json.dumps(rounded, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # Last resort: hash the entire record
    raw = json.dumps(vector_data, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _pick_keep_id(ids: list[str]) -> str:
    """Among duplicate IDs, pick the one to keep.

    Heuristic: keep the shortest ID (original upload) or alphabetically first.
    """
    return min(ids, key=lambda x: (len(x), x))


def find_duplicates(namespace: str) -> list[tuple[str, str, str]]:
    """Find duplicate vectors in a namespace.

    Returns list of (keep_id, duplicate_id, content_hash) tuples.
    """
    print(f"  Listing vectors in '{namespace}'...")
    ids = list_vector_ids(namespace)
    print(f"  Found {len(ids)} vectors")

    if len(ids) == 0:
        return []

    print(f"  Fetching vectors in batches of {FETCH_BATCH_SIZE}...")
    vectors = fetch_vectors(namespace, ids)
    print(f"  Fetched {len(vectors)} vectors")

    # Group by content hash
    hash_groups: dict[str, list[str]] = defaultdict(list)
    for vid, vdata in vectors.items():
        h = _content_hash(vdata)
        hash_groups[h].append(vid)

    # Find groups with more than one vector (= duplicates)
    duplicates: list[tuple[str, str, str]] = []
    for h, group_ids in hash_groups.items():
        if len(group_ids) > 1:
            keep_id = _pick_keep_id(group_ids)
            for dup_id in group_ids:
                if dup_id != keep_id:
                    duplicates.append((keep_id, dup_id, h))

    return duplicates


def delete_vectors(namespace: str, ids: list[str]) -> None:
    """Delete vectors by ID from a namespace."""
    if not ids:
        return

    resp = httpx.post(
        f"{INDEX_URL}/vectors/delete",
        headers=_headers(),
        json={"ids": ids, "namespace": namespace},
        timeout=30,
    )
    resp.raise_for_status()
    sleep(RATE_LIMIT_DELAY)


def delete_namespace(namespace: str) -> None:
    """Delete all vectors in a namespace (effectively deletes the namespace)."""
    resp = httpx.post(
        f"{INDEX_URL}/vectors/delete",
        headers=_headers(),
        json={"deleteAll": True, "namespace": namespace},
        timeout=30,
    )
    resp.raise_for_status()
    sleep(RATE_LIMIT_DELAY)


def describe_index_stats() -> dict:
    """Get index statistics including namespace vector counts."""
    resp = httpx.get(
        f"{INDEX_URL}/describe_index_stats",
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG Deduplication Tool for Pinecone kmd-knowledge index"
    )
    parser.add_argument("--namespace", type=str, help="Namespace to deduplicate")
    parser.add_argument(
        "--all", action="store_true", help="Check all known namespaces"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete duplicates (default: dry run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show duplicates without deleting (default)",
    )
    parser.add_argument(
        "--delete-namespace", type=str, help="Delete entire namespace"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show index statistics before and after",
    )
    args = parser.parse_args()

    if not PINECONE_API_KEY:
        print("ERROR: Set PINECONE_API_KEY environment variable")
        sys.exit(1)

    # --stats: show index statistics
    if args.stats:
        stats = describe_index_stats()
        print("\nIndex Statistics:")
        print(f"  Total vectors: {stats.get('totalVectorCount', 'N/A')}")
        namespaces = stats.get("namespaces", {})
        for ns_name, ns_info in sorted(namespaces.items()):
            print(f"  {ns_name}: {ns_info.get('vectorCount', '?')} vectors")
        print()

    # --delete-namespace: delete an entire namespace
    if args.delete_namespace:
        ns = args.delete_namespace
        if args.delete:
            print(f"Deleting namespace '{ns}'...")
            delete_namespace(ns)
            print(f"Deleted namespace: {ns}")
        else:
            print(f"Would delete namespace: {ns} (use --delete to confirm)")
        return

    # Determine which namespaces to check
    if args.all:
        namespaces = NAMESPACES_TO_CHECK
    elif args.namespace:
        namespaces = [args.namespace]
    else:
        parser.print_help()
        print("\nERROR: Specify --namespace, --all, or --delete-namespace")
        sys.exit(1)

    total_duplicates = 0

    for ns in namespaces:
        print(f"\n{'=' * 60}")
        print(f"Checking namespace: {ns}")
        print(f"{'=' * 60}")

        duplicates = find_duplicates(ns)

        if not duplicates:
            print(f"  No duplicates found in '{ns}'")
            continue

        print(f"\n  Found {len(duplicates)} duplicate(s):")
        for keep_id, dup_id, content_hash in duplicates:
            print(f"    KEEP:   {keep_id}")
            print(f"    DELETE: {dup_id}  (hash: {content_hash[:12]}...)")
            print()

        total_duplicates += len(duplicates)

        if args.delete:
            ids_to_delete = [dup_id for _, dup_id, _ in duplicates]
            print(f"  Deleting {len(ids_to_delete)} duplicates from '{ns}'...")
            delete_vectors(ns, ids_to_delete)
            print(f"  Deleted {len(ids_to_delete)} duplicates from '{ns}'")
        else:
            print(f"  Dry run — use --delete to remove duplicates")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Summary: {total_duplicates} total duplicate(s) across {len(namespaces)} namespace(s)")
    if not args.delete:
        print("Mode: DRY RUN (no changes made)")
    else:
        print("Mode: DELETE (duplicates removed)")
    print(f"{'=' * 60}")

    # Show post-deletion stats if we actually deleted something
    if args.delete and total_duplicates > 0:
        print("\nPost-deletion index statistics:")
        sleep(2)  # Wait for Pinecone to process deletions
        stats = describe_index_stats()
        namespaces_info = stats.get("namespaces", {})
        for ns_name in namespaces:
            ns_info = namespaces_info.get(ns_name, {})
            print(f"  {ns_name}: {ns_info.get('vectorCount', '?')} vectors")


if __name__ == "__main__":
    main()
