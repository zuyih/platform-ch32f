from SCons.Errors import UserError
from SCons.Script import Environment
import re

# setup clocks
def validate_and_define_sysclk(env: Environment):
    VALID_PLL_FREQS = {
        "ch32f10x": {
            "hsi+pll": [48_000_000, 56_000_000, 72_000_000],
            "hse+pll": [48_000_000, 56_000_000, 72_000_000],
        },
        "ch32f20x": {
            "hsi+pll": [48_000_000, 56_000_000, 72_000_000, 96_000_000, 120_000_000, 144_000_000],
            "hse+pll": [48_000_000, 56_000_000, 72_000_000, 96_000_000, 120_000_000, 144_000_000],
        },
    }

    ALLOWED_SOURCES = {"hsi", "hse", "hsi+pll", "hse+pll"}

    board_config = env.BoardConfig()
    spl_series = str(board_config.get("build.spl_series"))
    # CH57x: SystemInit() sets 32 MHz, the application can call SetSysClock()
    # and FREQ_SYS has to match it; no clock macro from the board
    if spl_series.startswith("ch5"):
        print(f"Skipping clock macro configuration for series {spl_series}.")
        return
    clock_source = str(board_config.get("build.clock_source"))
    f_cpu_str = str(board_config.get("build.f_cpu", "0"))

    match = re.match(r"\d+", f_cpu_str)
    if not match:
        raise UserError(f"Invalid f_cpu value: {f_cpu_str}")
    f_cpu = int(match.group(0))

    if clock_source not in ALLOWED_SOURCES:
        raise UserError(f"Invalid clock source: {clock_source}. Must be one of: {', '.join(sorted(ALLOWED_SOURCES))}")

    defines = []
    applied_macro, applied_freq = None, None

    if clock_source == "hsi":
        applied_macro = "SYSCLK_FREQ_HSI=HSI_VALUE"
        defines.append(("SYSCLK_FREQ_HSI", "HSI_VALUE"))
    elif clock_source == "hse":
        applied_macro = "SYSCLK_FREQ_HSE=HSE_VALUE"
        defines.append(("SYSCLK_FREQ_HSE", "HSE_VALUE"))
    elif clock_source in ("hsi+pll", "hse+pll"):
        if spl_series not in VALID_PLL_FREQS:
            raise UserError(f"Unknown SPL series '{spl_series}' for PLL frequency validation")

        valid_freqs = VALID_PLL_FREQS[spl_series][clock_source]
        if f_cpu not in valid_freqs:
            raise UserError(
                f"Invalid frequency {f_cpu} Hz for {clock_source} on {spl_series}. "
                f"Allowed: {', '.join(str(f) for f in valid_freqs)}"
            )

        macro_name = f"SYSCLK_FREQ_{f_cpu // 1_000_000}MHz_{'HSI' if clock_source.startswith('hsi') else 'HSE'}"
        defines.append((macro_name, f_cpu))
        applied_macro = f"{macro_name}={f_cpu}"
        applied_freq = f_cpu

    env.Append(CPPDEFINES=defines)

    print("Clock configuration:")
    print(f"  Source: {clock_source}")
    if applied_freq:
        print(f"  Frequency: {applied_freq} Hz")
    print(f"  Macro: {applied_macro}")
