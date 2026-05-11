# Proguard rules — kept minimal in Sprint 3 because release is not the
# acceptance gate. Real shrinking config will be added in Sprint 10 when
# we sign a release build for in-store beta.

# Keep generated Hilt classes (DI graph is reflective at compose-runtime boundary).
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.android.HiltAndroidApp

# Keep Room generated DAO implementations.
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Database class *

# kotlinx.serialization — generated $$serializer companions.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keep,includedescriptorclasses class ru.slicepizza.restforest.**$$serializer { *; }
-keepclassmembers class ru.slicepizza.restforest.** { *** Companion; }
-keepclasseswithmembers class ru.slicepizza.restforest.** { kotlinx.serialization.KSerializer serializer(...); }
