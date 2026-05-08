"""
device_spec_loader.py
YAML 스펙 파일 → DeviceSpec 구조체 빌드
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SPECS_DIR = Path(__file__).parent / "specs"
COMMANDS_DIR = SPECS_DIR / "commands"
DEVICES_DIR = SPECS_DIR / "devices"


# ---------------------------------------------------------------------------
# 데이터 구조체
# ---------------------------------------------------------------------------

@dataclass
class CmdEntry:
    cmd: str
    description: str
    regex: str
    values: dict[str, str]      # {"0": "Static IP", ...}
    access: str                 # "RO" / "RW" / "WO"
    ui: dict[str, Any] | None   # tab/group/widget 정보 (None = UI 없음)

    def is_readable(self) -> bool:
        return self.access in ("RO", "RW")

    def is_writable(self) -> bool:
        return self.access in ("RW", "WO")

    def is_valid(self, value: str) -> bool:
        """regex가 빈 문자열이면 항상 유효 (자유 입력)."""
        if not self.regex:
            return True
        if self.cmd == "RH":
            return True  # 도메인명 허용
        return bool(re.match(self.regex, value))

    def get_display(self, value: str) -> str:
        """values 맵에 있으면 설명 문자열, 없으면 값 그대로."""
        if value in self.values:
            return self.values[value]
        return value


@dataclass
class FWConfig:
    upload_supported: bool = False
    config_port: int = 50001
    upload_port_from_response: bool = False
    hw_version_field: str = "VR"
    new_hw_major_versions: list[int] = field(default_factory=list)
    new_fw_effective_size: int = 0
    old_fw_max_size: int = 0
    version_specific: list[dict] = field(default_factory=list)


@dataclass
class UITabConfig:
    tab_id: str
    label: str
    groups: list[str]


@dataclass
class UIConfig:
    tabs: list[UITabConfig]


@dataclass
class DeviceSpec:
    name: str
    display_name: str
    aliases: list[str]
    family: str
    channels: int
    cmdset: dict[str, CmdEntry]       # {cmd: CmdEntry}
    search_cmd_list: list[str]        # 검색 패킷에 포함될 커맨드 순서
    fw_config: FWConfig
    ui_config: UIConfig


# ---------------------------------------------------------------------------
# 로더
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_command_group(group_name: str) -> dict[str, CmdEntry]:
    """commands/<group>.yaml 로드 → {cmd: CmdEntry} 반환."""
    path = COMMANDS_DIR / f"{group_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Command group not found: {path}")
    raw = _load_yaml(path)
    result: dict[str, CmdEntry] = {}
    for cmd, spec in raw.items():
        result[cmd] = CmdEntry(
            cmd=cmd,
            description=spec.get("description", ""),
            regex=spec.get("regex", ""),
            values=spec.get("values", {}) or {},
            access=spec.get("access", "RW"),
            ui=spec.get("ui"),
        )
    return result


def _apply_overrides(cmdset: dict[str, CmdEntry], overrides: dict) -> None:
    """device overrides를 cmdset에 덮어씌운다."""
    for cmd, ovr in overrides.items():
        if cmd in cmdset:
            entry = cmdset[cmd]
            if "regex" in ovr:
                entry.regex = ovr["regex"]
            if "values" in ovr:
                # 문자열 키 강제 (YAML이 정수로 읽을 수 있음)
                entry.values = {str(k): str(v) for k, v in ovr["values"].items()}
        else:
            # override 대상 커맨드가 없으면 새로 추가
            cmdset[cmd] = CmdEntry(
                cmd=cmd,
                description=ovr.get("description", ""),
                regex=ovr.get("regex", ""),
                values={str(k): str(v) for k, v in ovr.get("values", {}).items()},
                access=ovr.get("access", "RW"),
                ui=ovr.get("ui"),
            )


def load_device(device_name: str, fw_version: str | None = None) -> DeviceSpec:
    """
    devices/<device_name>.yaml 로드 + command_groups 병합 + overrides 적용.
    fw_version: 버전별 override 적용 시 사용 (예: "1.2.0")
    """
    path = DEVICES_DIR / f"{device_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Device spec not found: {path}")

    dev = _load_yaml(path)

    # 1. 커맨드 그룹 병합 (순서 중요 — 뒤 그룹이 앞 그룹을 override)
    cmdset: dict[str, CmdEntry] = {}
    for group in dev.get("command_groups", []):
        cmdset.update(_load_command_group(group))

    # 2. device-level overrides 적용
    if "overrides" in dev:
        _apply_overrides(cmdset, dev["overrides"])

    # 3. fw_version 기반 version_specific overrides 적용
    fw_raw = dev.get("fw_constraints", {})
    if fw_version and "version_specific" in fw_raw:
        from packaging.version import Version
        try:
            fw_ver = Version(fw_version)
        except Exception:
            fw_ver = None
        if fw_ver:
            for rule in fw_raw["version_specific"]:
                condition = rule.get("condition", "")
                if _check_version_condition(fw_ver, condition):
                    _apply_overrides(cmdset, rule.get("overrides", {}))

    # 4. search_cmd_list
    search_cmd_list: list[str] = dev.get("search_cmd_order", [])
    if not search_cmd_list:
        # fallback: cmdset에서 RO/RW 커맨드만 (WO 제외)
        search_cmd_list = [c for c, e in cmdset.items() if e.is_readable()]

    # 5. FWConfig
    fw_config = FWConfig(
        upload_supported=fw_raw.get("upload_supported", False),
        config_port=fw_raw.get("config_port", 50001),
        upload_port_from_response=fw_raw.get("upload_port_from_response", False),
        hw_version_field=fw_raw.get("hw_version_field", "VR"),
        new_hw_major_versions=fw_raw.get("new_hw_major_versions", []),
        new_fw_effective_size=fw_raw.get("new_fw_effective_size", 0),
        old_fw_max_size=fw_raw.get("old_fw_max_size", 0),
        version_specific=fw_raw.get("version_specific", []),
    )

    # 6. UIConfig
    ui_raw = dev.get("ui", {})
    tabs: list[UITabConfig] = []
    for tab in ui_raw.get("tabs", []):
        tabs.append(UITabConfig(
            tab_id=tab["id"],
            label=tab["label"],
            groups=tab.get("groups", []),
        ))
    ui_config = UIConfig(tabs=tabs)

    return DeviceSpec(
        name=dev["name"],
        display_name=dev.get("display_name", dev["name"]),
        aliases=dev.get("aliases", [dev["name"]]),
        family=dev.get("family", "one_port"),
        channels=dev.get("channels", 1),
        cmdset=cmdset,
        search_cmd_list=search_cmd_list,
        fw_config=fw_config,
        ui_config=ui_config,
    )


def _check_version_condition(fw_ver: Any, condition: str) -> bool:
    """'VR < 1.2.1' 형태의 조건 파싱."""
    try:
        from packaging.version import Version
        # 예: "VR < 1.2.1"
        parts = condition.split()
        if len(parts) == 3 and parts[0] == "VR":
            op = parts[1]
            cmp_ver = Version(parts[2])
            if op == "<":
                return fw_ver < cmp_ver
            elif op == "<=":
                return fw_ver <= cmp_ver
            elif op == ">":
                return fw_ver > cmp_ver
            elif op == ">=":
                return fw_ver >= cmp_ver
            elif op == "==":
                return fw_ver == cmp_ver
    except Exception:
        pass
    return False


def detect_device(mn_value: str) -> str | None:
    """
    MN 응답값으로 device name 감지.
    모든 device yaml의 aliases를 검색.
    """
    for yaml_file in DEVICES_DIR.glob("*.yaml"):
        dev = _load_yaml(yaml_file)
        for alias in dev.get("aliases", []):
            if alias.upper() == mn_value.strip().upper():
                return dev["name"]
    return None


def list_devices() -> list[str]:
    """지원 장비 이름 목록 반환."""
    result = []
    for yaml_file in sorted(DEVICES_DIR.glob("*.yaml")):
        dev = _load_yaml(yaml_file)
        result.append(dev["name"])
    return result


# ---------------------------------------------------------------------------
# 단독 실행 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== 지원 장비 목록 ===")
    for name in list_devices():
        print(f"  {name}")

    print("\n=== WIZ107SR 스펙 로드 ===")
    spec = load_device("WIZ107SR")
    print(f"  name: {spec.name}")
    print(f"  family: {spec.family}")
    print(f"  channels: {spec.channels}")
    print(f"  cmdset keys ({len(spec.cmdset)}): {list(spec.cmdset.keys())}")
    print(f"  search_cmd_list ({len(spec.search_cmd_list)}): {spec.search_cmd_list}")
    print(f"  UI tabs: {[t.tab_id for t in spec.ui_config.tabs]}")

    print("\n=== DB override 확인 (9-bit) ===")
    db = spec.cmdset["DB"]
    print(f"  DB regex: {db.regex}")
    print(f"  DB values: {db.values}")

    print("\n=== BR override 확인 (최대 230400) ===")
    br = spec.cmdset["BR"]
    print(f"  BR regex: {br.regex}")
    print(f"  BR values: {br.values}")

    print("\n=== detect_device 테스트 ===")
    print(f"  'WIZ107SR' → {detect_device('WIZ107SR')}")
    print(f"  'WIZ750SR' → {detect_device('WIZ750SR')}")
    print(f"  'unknown'  → {detect_device('unknown')}")
