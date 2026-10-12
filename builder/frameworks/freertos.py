from os.path import isdir, join
from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()

# import NoneOS SDK settings
env.SConscript("noneos_sdk.py")

FRAMEWORK_DIR = platform.get_package_dir("framework-wch-arm-sdk")
assert isdir(FRAMEWORK_DIR)
# one FreeRTOS kernel for all series, the port is selected by the core
FREERTOS_DIR = join(FRAMEWORK_DIR, "RTOS", "FreeRTOS")

env.Append(
    CPPPATH=[
        join(FREERTOS_DIR, "include"),
        join(FREERTOS_DIR, "portable", "Common"),
        join(FREERTOS_DIR, "portable", "GCC", "ARM_CM3"),
        join(FREERTOS_DIR, "portable", "MemMang"),
        FREERTOS_DIR,
        # user will likely have the FreeRTOSConfig.h located in the main source directory, so include it for the build too
        "$PROJECT_SRC_DIR",
        "$PROJECT_INCLUDE_DIR"
    ],
    CPPDEFINES=[
        "__PIO_BUILD_FREERTOS__"
    ]
)

env.BuildSources(
    join("$BUILD_DIR", "FrameworkFreeRTOSCore"),
    FREERTOS_DIR,
    # Just like the IDE, we do not build MPU Wrappers
    "+<*> -<%s>" % join("portable", "Common", "mpu_wrappers.c")
)
