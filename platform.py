# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from platformio.public import PlatformBase


class Ch32fPlatform(PlatformBase):
    # WCH-Link(E) in ARM mode is a CMSIS-DAP probe as well
    OPENOCD_TOOLS = ("wch-link", "cmsis-dap")
    # USB IDs of the WCH-Links in DAP mode: LinkDAP-WINUSB (all models) and
    # LinkDAP-HID (WCH-DAPLink only). RV mode (1a86:8010) is no CMSIS-DAP.
    WCH_LINK_USB_IDS = ("0x1a86 0x8012", "0x1a86 0x8011")

    def configure_default_packages(self, variables, targets):
        if variables.get("board"):
            board_config = self.board_config(variables.get("board"))
            default_protocol = board_config.get("upload.protocol") or ""
            upload_protocol = variables.get("upload_protocol", default_protocol)
            # PlatformIO installs every uploader package for the upload
            # target, so drop the ones this project can not use.
            # wchisp is only needed to upload via USB bootloader (called "isp"
            # in our platform)
            if upload_protocol != "isp":
                self.packages.pop("tool-wchisp", None)
            # OpenOCD drives the CMSIS-DAP probes for upload and debug
            # (installed on demand by the debugger). Chips without OpenOCD
            # support (CH579) never need it.
            if not board_config.get("debug.openocd_target", "") and upload_protocol not in self.OPENOCD_TOOLS:
                self.packages.pop("tool-openocd", None)
        return super().configure_default_packages(variables, targets)

    def get_boards(self, id_=None):
        result = super().get_boards(id_)
        if not result:
            return result
        if id_:
            return self._add_default_debug_tools(result)
        else:
            for key in result:
                result[key] = self._add_default_debug_tools(result[key])
        return result

    def _add_default_debug_tools(self, board):
        debug = board.manifest.get("debug", {})
        if "tools" not in debug:
            debug["tools"] = {}

        # CMSIS-DAP probes (WCH-Link(E) in ARM mode, DAPLink, ...) through
        # OpenOCD. The CH32F flash is programmed by the wch_arm driver.
        # Chips without OpenOCD support (CH579) have no openocd_target.
        upload_protocols = board.manifest.get("upload", {}).get("protocols", [])
        for tool in self.OPENOCD_TOOLS:
            if tool not in upload_protocols or tool in debug["tools"] or not debug.get("openocd_target"):
                continue
            server_args = [
                "-s", "$PACKAGE_DIR/openocd/scripts",
                "-f", "interface/cmsis-dap.cfg",
            ]
            # wch-link only connects to a WCH-Link, cmsis-dap to any probe
            if tool == "wch-link":
                server_args.extend(
                    ["-c", "adapter usb vid_pid %s" % " ".join(self.WCH_LINK_USB_IDS)]
                )
            server_args.extend(["-c", "transport select swd"])
            server_args.extend(["-f", "target/%s.cfg" % debug.get("openocd_target")])
            server_args.extend(debug.get("openocd_extra_args", []))
            debug["tools"][tool] = {
                "server": {
                    "package": "tool-openocd",
                    "executable": "bin/openocd",
                    "arguments": server_args,
                }
            }
            debug["tools"][tool]["onboard"] = tool in debug.get("onboard_tools", [])
            debug["tools"][tool]["default"] = tool in debug.get("default_tools", [])

        board.manifest["debug"] = debug
        return board

    def configure_debug_session(self, debug_config):
        if debug_config.speed:
            if "openocd" in (debug_config.server or {}).get("executable", ""):
                debug_config.server["arguments"].extend(
                    ["-c", "adapter speed %s" % debug_config.speed]
                )
