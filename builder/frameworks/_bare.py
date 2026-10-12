import os
from SCons.Script import DefaultEnvironment
from common_clk_config import validate_and_define_sysclk

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

machine_flags = [
    "-mcpu=%s" % board.get("build.cpu"),
    "-mthumb",
]

def get_flag_value(flag_name:str, default_val:bool):
    flag_val = board.get("build.%s" % flag_name, default_val)
    flag_val = str(flag_val).lower() in ("1", "yes", "true")
    return flag_val

lto_flag = ""
if get_flag_value("use_lto", False):
    lto_flag = "-flto"

abi_flags = []
if str(board.get("build.spl_series", "")).startswith("ch5"):
    # the prebuilt libraries of the CH57x EVT (BLE, network) are compiled
    # by ARM Compiler 5 with enums as small as possible
    abi_flags.append("-fshort-enums")

env.Append(
    ASFLAGS=machine_flags,
    ASPPFLAGS=[
        "-x", "assembler-with-cpp",
    ],

    CFLAGS=[
        "-std=gnu99"
    ],

    CXXFLAGS=[
        # compiler goes up to gnu++2a but is EXPERIMENTAL
        "-std=gnu++17",
        # standard embedded flags to reduce firmware size
        "-fno-threadsafe-statics",
        "-fno-rtti",
        "-fno-exceptions",
        "-fno-use-cxa-atexit"
    ],

    CCFLAGS=[
        "-Os",
        "-g",
        "-Wall",
        "-fmessage-length=0",
        "-fsigned-char",
        "-ffunction-sections",
        "-fdata-sections",
        "-fno-common",
        "-Wunused",
        "-Wuninitialized",
        "-Wno-comment",
        lto_flag,
    ] + abi_flags + machine_flags,

    LIBS=[
        "m" # math library linked by default
    ],

    LINKFLAGS=[
        "-Os",
        "-g",
        "-ffunction-sections",
        "-fdata-sections",
        "-Wl,-gc-sections",
        "--specs=nano.specs",
        "--specs=nosys.specs",
        "-nostartfiles",
        lto_flag,
    ] + machine_flags
)

# Automatically create map file, unless user already creates a map file at a different place
# using their own build_flags.
if not any("-Wl,-Map" in f for f in env.get("LINKFLAGS", [])):
    env.Append(LINKFLAGS=[
        '-Wl,-Map="%s"' % os.path.join("${BUILD_DIR}", "${PROGNAME}.map")
    ])

# copy general C/C++ flags to assembler with cpp flags too, except
# would-be-duplicate machine flags
env["ASPPFLAGS"].extend(env["CCFLAGS"][:-len(machine_flags)])

# add sysclock defines
validate_and_define_sysclk(env)
