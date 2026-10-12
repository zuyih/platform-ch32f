from os.path import isdir, join
from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()
chip_series: str = board.get("build.spl_series", "")

# import NoneOS SDK settings
env.SConscript("noneos_sdk.py")

FRAMEWORK_DIR = platform.get_package_dir("framework-wch-arm-sdk")
assert isdir(FRAMEWORK_DIR)
# one RT-Thread kernel for all series, only board.h is per series
RTTHREAD_DIR = join(FRAMEWORK_DIR, "RTOS", "RT-Thread")

env.Append(
    CPPPATH=[
        join(RTTHREAD_DIR, "bsp", chip_series),
        join(RTTHREAD_DIR, "include"),
        join(RTTHREAD_DIR, "include", "libc"),
        join(RTTHREAD_DIR, "src"),
        RTTHREAD_DIR,
        join(RTTHREAD_DIR, "drivers"),
        join(RTTHREAD_DIR, "libcpu", "arm", "cortex-m3"),
        join(RTTHREAD_DIR, "components", "drivers", "include"),
        join(RTTHREAD_DIR, "components", "drivers", "misc"),
        join(RTTHREAD_DIR, "components", "drivers", "serial"),
        join(RTTHREAD_DIR, "components", "finsh"),
        # ch32f_it.h is mandatory for RT-Thread to build, this will likely be included
        # in the user's directory.
        "$PROJECT_SRC_DIR",
        "$PROJECT_INCLUDE_DIR"
    ],
    CPPDEFINES=[
        # the startup.S file jumps to the RT-Thread entry point instead of main()
        "__PIO_BUILD_RT_THREAD__",
        # memory sizes of the chip for board.h
        ("CH32_FLASH_SIZE", board.get("upload.maximum_size")),
        ("CH32_SRAM1_SIZE", int(board.get("upload.maximum_ram_size")) // 1024),
    ]
)

# the pin driver has pin maps for these package pin counts only
pin_count = int(board.get("build.pin_count", 0))
if pin_count in (36, 48, 64, 100):
    env.Append(CPPDEFINES=[("CH32F20X_PIN_NUMBERS", pin_count)])
else:
    print("Warning: RT-Thread pin driver has no pin map for %d pins, using the board.h default" % pin_count)

env.BuildSources(
    join("$BUILD_DIR", "FrameworkRTThreadCore"),
    RTTHREAD_DIR,
    # board.h of the other series is not needed
    "+<*> -<bsp>"
)
