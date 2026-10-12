"""Generate the generic board definitions in boards/ from the WCH product tables."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import json

@dataclass
class WCHChipSeries:
    name: str # e.g. CH32F20x
    cpu: str # e.g. cortex-m3
    svd_file: str # e.g. CH32F203xx.svd
    spl_series: str
    freq_mhz: int # default system clock
    url: str
    frameworks: List[str] = field(default_factory=lambda: ["noneos-sdk", "freertos", "rt-thread"])
    flash_start: str = "0x08000000"
    # upload and debug through CMSIS-DAP probes (WCH-Link in ARM mode,
    # DAPLink, ...) and OpenOCD, or upload through the USB bootloader with
    # wchisp. CH32F is programmed by the wch_arm driver of OpenOCD.
    openocd_target: Optional[str] = "ch32f1x"
    upload_protocols: List[str] = field(default_factory=lambda: ["wch-link", "cmsis-dap", "isp"])

CH32F103 = WCHChipSeries("CH32F10x", "cortex-m3", "CH32F103xx.svd", "ch32f10x", 72, "https://www.wch.cn/products/CH32F103.html")
CH32F203_D6 = WCHChipSeries("CH32F20x", "cortex-m3", "CH32F203xx.svd", "ch32f20x", 144, "https://www.wch.cn/products/CH32F203C8.html")
CH32F203_D8 = WCHChipSeries("CH32F20x", "cortex-m3", "CH32F203xx.svd", "ch32f20x", 144, "https://www.wch.cn/products/CH32F203.html")
CH32F207 = WCHChipSeries("CH32F20x", "cortex-m3", "CH32F203xx.svd", "ch32f20x", 144, "https://www.wch.cn/products/CH32F207.html")
CH32F208 = WCHChipSeries("CH32F20x", "cortex-m3", "CH32F203xx.svd", "ch32f20x", 144, "https://www.wch.cn/products/CH32F208.html")
# CH579: SystemInit() sets 32 MHz. The OpenOCD fork of WCH has no flash
# driver for it, upload through the USB bootloader (wchisp) only.
CH579 = WCHChipSeries("CH579", "cortex-m0", "CH579SFR.svd", "ch579", 32, "https://www.wch.cn/products/CH579.html",
                      frameworks=["noneos-sdk"], flash_start="0x00000000", openocd_target=None,
                      upload_protocols=["isp"])

PACKAGE_PINS = {
    "QFN28": 28,
    "LQFP32": 32,
    "LQFP48": 48,
    "QFN48": 48,
    "QFN48X7": 48,
    "LQFP64M": 64,
    "QFN68": 68,
    "LQFP100": 100,
}

@dataclass
class ChipInfo:
    name: str
    flash_kb: int
    sram_kb: int
    package: str
    chip_type: WCHChipSeries

    def get_classification_macro(self) -> Optional[str]:
        # see the device classes in ch32f20x.h
        dev_classes = {
            "CH32F20x_D6": ["CH32F203K8", "CH32F203C6", "CH32F203C8"],
            "CH32F20x_D8": ["CH32F203CB", "CH32F203RB", "CH32F203RC", "CH32F203VC"],
            "CH32F20x_D8C": ["CH32F205RB", "CH32F207VC"],
            "CH32F20x_D8W": ["CH32F208RB", "CH32F208WB"],
        }
        for macro, chips in dev_classes.items():
            if self.chip_without_package() in chips:
                return macro
        return None

    def is_ch5(self) -> bool:
        return self.name.lower().startswith("ch5")

    def chip_without_package(self) -> str:
        if self.is_ch5():
            return self.name[0:len("ch5xx")].upper()
        return self.name[0:len("ch32fxxxxx")].upper()

    def exact_series(self) -> str:
        if self.is_ch5():
            return self.name[0:len("ch5xx")]
        return self.name[0:len("ch32fxxx")]

# Part list of the "Cortex-M通用系列" table on wch.cn
# and the CH579 datasheet (CH579DS1.PDF)
chip_db = [
    ChipInfo("CH32F103C6T6", 32, 10, "LQFP48", CH32F103),
    ChipInfo("CH32F103C8U6", 64, 20, "QFN48X7", CH32F103),
    ChipInfo("CH32F103C8T6", 64, 20, "LQFP48", CH32F103),
    ChipInfo("CH32F103R8T6", 64, 20, "LQFP64M", CH32F103),
    ChipInfo("CH32F203C6T6", 32, 10, "LQFP48", CH32F203_D6),
    ChipInfo("CH32F203K8T6", 64, 20, "LQFP32", CH32F203_D6),
    ChipInfo("CH32F203C8T6", 64, 20, "LQFP48", CH32F203_D6),
    ChipInfo("CH32F203C8U6", 64, 20, "QFN48X7", CH32F203_D6),
    ChipInfo("CH32F203CBT6", 128, 32, "LQFP48", CH32F203_D8),
    ChipInfo("CH32F203RBT6", 128, 32, "LQFP64M", CH32F203_D8),
    ChipInfo("CH32F203RCT6", 256, 64, "LQFP64M", CH32F203_D8),
    ChipInfo("CH32F203VCT6", 256, 64, "LQFP100", CH32F203_D8),
    ChipInfo("CH32F205RBT6", 128, 32, "LQFP64M", CH32F207),
    ChipInfo("CH32F207VCT6", 256, 64, "LQFP100", CH32F207),
    ChipInfo("CH32F208RBT6", 128, 64, "LQFP64M", CH32F208),
    ChipInfo("CH32F208WBU6", 128, 64, "QFN68", CH32F208),
    ChipInfo("CH579M", 250, 32, "QFN48", CH579),
    ChipInfo("CH579F", 250, 32, "QFN28", CH579),
]

def create_board_json(info: ChipInfo, board_name:str, output_path: Path, patch_info: Optional[Dict[str, Any]] = None, clock_source: str = "hsi+pll"):
    series = info.chip_type
    base_json = {
        "build": {
            "cpu": series.cpu,
            "f_cpu": str(series.freq_mhz * 1000_000) + "L",
            "mcu": info.name.lower(),
            "pin_count": PACKAGE_PINS[info.package],
            "series": info.exact_series().lower(),
            "spl_series": series.spl_series,
        },
        "debug": {
            "svd_path": series.svd_file
        },
        "frameworks": series.frameworks[:],
        "name": board_name,
        "upload": {
            "maximum_ram_size": info.sram_kb * 1024,
            "maximum_size": info.flash_kb * 1024,
            "offset_address": series.flash_start,
            "protocols": series.upload_protocols[:],
            "protocol": series.upload_protocols[0]
        },
        "url": series.url,
        "vendor": "W.CH"
    }
    if not info.is_ch5():
        # the clock of the CH57x is set up by the application
        base_json["build"]["clock_source"] = clock_source
    if series.openocd_target:
        base_json["debug"]["onboard_tools"] = ["wch-link"]
        base_json["debug"]["openocd_target"] = series.openocd_target
    # add some classification macros
    if info.is_ch5():
        extra_flags = [
            f"-D{info.chip_without_package()}",
            f"-D{info.name[0:len('ch5x')]}X",
            f"-D{info.name[0:len('ch5x')]}x",
        ]
    else:
        extra_flags = [
            f"-D{info.chip_without_package()}",
            f"-D{info.name[0:len('ch32fxx')]}X",
            f"-D{info.name[0:len('ch32fxx')]}x",
            f"-D{info.name[0:len('ch32fxxx')]}",
        ]
    classification_macro = info.get_classification_macro()
    if classification_macro is not None:
        extra_flags += ["-D" + classification_macro]
    base_json["build"]["extra_flags"] = " ".join(extra_flags)
    if patch_info is not None:
        for k, v in patch_info.items():
            # upmost level
            if k.count(".") == 0:
                base_json[k] = v
            # one deeper (e.g. build.extra_flags)
            if k.count(".") == 1:
                k1, k2 = k.split(".")
                base_json[k1][k2] = v
    as_str = json.dumps(base_json, indent=2, sort_keys=True) + "\n"
    print("DEFINITION FOR %s:\n%s" % (board_name, as_str))
    output_path.write_text(as_str, encoding='utf-8')


def main():
    # generate board JSON for all known chips directly into boards folder
    base_path = Path(__file__).parents[2].resolve() / "boards"
    base_path.mkdir(exist_ok=True)
    for info in chip_db:
        output_path = base_path / f"generic{info.name.upper()}.json"
        create_board_json(info, f"Generic {info.name.upper()}", output_path)


if __name__ == '__main__':
    main()
