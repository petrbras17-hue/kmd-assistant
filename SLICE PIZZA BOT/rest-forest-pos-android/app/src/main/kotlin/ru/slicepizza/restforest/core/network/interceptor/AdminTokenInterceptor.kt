package ru.slicepizza.restforest.core.network.interceptor

import okhttp3.Interceptor
import okhttp3.Response

/**
 * Adds X-Admin-Token to every backend request. Empty token (release builds
 * pre-config) → skip header so requests still reach health endpoints.
 */
class AdminTokenInterceptor(private val tokenProvider: () -> String) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenProvider()
        val req = if (token.isBlank()) chain.request()
                  else chain.request().newBuilder()
                      .addHeader("X-Admin-Token", token)
                      .build()
        return chain.proceed(req)
    }
}
