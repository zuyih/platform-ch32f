from os.path import isdir, isfile, join, dirname, realpath, isabs
from string import Template
from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()
# for a MCU name (e.g. "ch32f203c8t6") we need the series (e.g. "ch32f20x")
chip_series: str = board.get("build.spl_series", "")
# import default build settings
env.SConscript("_bare.py")

FRAMEWORK_DIR = platform.get_package_dir("framework-wch-arm-sdk")
assert isdir(FRAMEWORK_DIR)

# helper vars
has_system_code = not chip_series.startswith("ch5")
has_debug_code = not chip_series.startswith("ch5")

def get_flag_value(flag_name:str, default_val:bool):
    flag_val = board.get("build.%s" % flag_name, default_val)
    flag_val = str(flag_val).lower() in ("1", "yes", "true")
    return flag_val

# the linker script also uses $ on it, so we can't use that as the
# variable identifier for the substitution engine.
class CustomTemplate(Template):
	delimiter = "#"

def get_linker_script() -> str:
    default_ldscript = join(env.subst("$BUILD_DIR"), "Link.ld")

    ram = board.get("upload.maximum_ram_size", 0)
    flash = board.get("upload.maximum_size", 0)
    flash_start = int(board.get("upload.offset_address", "0x08000000"), 0)
    stack_size = 2048
    # custom stack size wanted?
    if board.get("build.stack_size", "") != "":
        stack_size = int(board.get("build.stack_size"))
    template_file = join(FRAMEWORK_DIR, "platformio",
                         "ldscripts", "Link.tpl")
    content = ""
    with open(template_file) as fp:
        data = CustomTemplate(fp.read())
        content = data.substitute(
            stack=hex(0x20000000 + ram), # 0x20000000 - start address for RAM
            ram=str(int(ram/1024)) + "K",
            flash=str(int(flash/1024)) + "K",
            flash_start=hex(flash_start),
            stack_size=stack_size
        )

    with open(default_ldscript, "w") as fp:
        fp.write(content)

    return default_ldscript

def get_startup_filename(board):
    # the gen_boarddefs.py already put the classification macro
    # into the extra_flags. Read them again and map them onto the startup files.
    extra_flags = str(board.get("build.extra_flags", "")).split(" ")
    class_to_startup = {
        "CH32F20x_D6": "startup_ch32f20x_D6.S",
        "CH32F20x_D8": "startup_ch32f20x_D8.S",
        "CH32F20x_D8C": "startup_ch32f20x_D8C.S",
        "CH32F20x_D8W": "startup_ch32f20x_D8W.S",
    }
    startup_file = None
    for k, v in class_to_startup.items():
        if any([f"-D{k}" == flag for flag in extra_flags]):
            startup_file = v
    if startup_file is None and chip_series in ("ch32f10x", "ch579"):
        startup_file = "startup_%s.S" % chip_series
    if startup_file is None:
        print("Failed to find startup file for board " + str(board))
        env.Exit(-1)
    return startup_file

env.Append(
    CPPPATH=[
        join(FRAMEWORK_DIR, "Core", chip_series),
        join(FRAMEWORK_DIR, "Peripheral", chip_series, "inc"),
        join(FRAMEWORK_DIR, "Peripheral", chip_series, "src")
        # Paths for startup and system are addeed later if wanted
    ]
)

if not board.get("build.ldscript", ""):
    env.Replace(LDSCRIPT_PATH=get_linker_script())

libs = []

env.BuildSources(
    join("$BUILD_DIR", "FrameworkNoneOSCore"),
    join(FRAMEWORK_DIR, "Core", chip_series)
)

startup_filename = board.get("build.startup", None)
if startup_filename :
    # evaluate possible variables in the path
    startup_filename = env.subst(startup_filename)
    # if not absolute path, assume relative to project dir.
    if not isabs(startup_filename):
        startup_filename = join(env.subst("$PROJECT_DIR"), startup_filename)
    startup_filename = realpath(startup_filename)
    env.Append(CPPPATH=[dirname(startup_filename)])
    print("Using custom startup file: %s" % startup_filename)
    if not isfile(startup_filename):
        print("Provided startup file not found: %s" % startup_filename)
        env.Exit(-1)
    env.BuildSources(
        join("$BUILD_DIR", "ProjectStartup"),
        dirname(startup_filename),
        "-<*> +<%s>" % startup_filename
    )
elif get_flag_value("use_builtin_startup_file", True):
    env.Append(CPPPATH=[join(FRAMEWORK_DIR, "Startup")])
    env.BuildSources(
        join("$BUILD_DIR", "FrameworkNoneOSStartup"),
        join(FRAMEWORK_DIR, "Startup"),
        "-<*> +<%s>" % get_startup_filename(board)
    )

# for clock init etc.
if get_flag_value("use_builtin_system_code", True) and has_system_code:
    env.Append(CPPPATH=[join(FRAMEWORK_DIR, "System", chip_series)])
    env.BuildSources(
        join("$BUILD_DIR", "FrameworkNoneOSSSystem"),
        join(FRAMEWORK_DIR, "System", chip_series)
    )

# By default, include the Debug.h/.c code.
# practically every example needs it. Can be turned of in the platformio.ini.
if get_flag_value("use_builtin_debug_code", True) and has_debug_code:
    env.Append(CPPPATH=[join(FRAMEWORK_DIR, "Debug", chip_series)])
    env.BuildSources(
        join("$BUILD_DIR", "FrameworkNoneOSDebug"),
        join(FRAMEWORK_DIR, "Debug", chip_series)
    )

# Auto-compile in empty _init() and _fini() functions for C++ support
if get_flag_value("cpp_support", True):
    env.Append(CPPDEFINES=["__PIO_CPP_SUPPORT__"])
    env.BuildSources(
        join("$BUILD_DIR", "FrameworkInitFini"),
        join(FRAMEWORK_DIR, "CPP_Support")
    )

libs.append(env.BuildLibrary(
    join("$BUILD_DIR", "FrameworkNoneOSVariant"),
    join(FRAMEWORK_DIR, "Peripheral", chip_series, "src")
))

env.Append(LIBS=libs)
