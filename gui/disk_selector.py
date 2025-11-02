"""
Disk Selector Widget - Select source and target disks
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class DiskSelectorFrame(ttk.Frame):
    """Widget for selecting source and target disks"""

    def __init__(self, parent, disk_manager, on_source_selected=None, on_target_selected=None, main_window=None):
        super().__init__(parent)

        self.disk_manager = disk_manager
        self.on_source_selected = on_source_selected
        self.on_target_selected = on_target_selected
        self.main_window = main_window

        self.source_disk = None
        self.target_disk = None
        self.disk_map = {}

        self._create_widgets()
        self._layout_widgets()

    def _create_widgets(self):
        """Create widgets"""

        # Refresh button
        self.refresh_button = ttk.Button(
            self,
            text="🔄 刷新磁盘",
            command=self._refresh_disks,
            bootstyle=SECONDARY,
            width=20
        )

        # Source disk section
        self.source_label = ttk.Label(
            self,
            text="源SD卡:",
            font=("Segoe UI", 10, "bold")
        )

        self.source_combobox = ttk.Combobox(
            self,
            state="readonly",
            width=25
        )
        self.source_combobox.bind("<<ComboboxSelected>>", self._on_source_selected)

        self.source_info = ttk.Label(
            self,
            text="未选择\n\n",  # Pre-allocate 3 lines with blank lines
            font=("Segoe UI", 9),
            bootstyle=INFO  # Blue color like the info panel on the right
        )

        # Separator
        self.separator1 = ttk.Separator(self, orient=HORIZONTAL)

        # Target disk section
        self.target_label = ttk.Label(
            self,
            text="目标SD卡:",
            font=("Segoe UI", 10, "bold")
        )

        self.target_combobox = ttk.Combobox(
            self,
            state="readonly",
            width=25
        )
        self.target_combobox.bind("<<ComboboxSelected>>", self._on_target_selected)

        self.target_info = ttk.Label(
            self,
            text="未选择\n\n",  # Pre-allocate 3 lines with blank lines
            font=("Segoe UI", 9),
            bootstyle=INFO  # Blue color like the info panel on the right
        )

        # Warning label
        self.warning_label = ttk.Label(
            self,
            text="⚠️ 目标磁盘将被清空!",
            font=("Segoe UI", 9, "bold"),
            bootstyle=DANGER
        )

    def _layout_widgets(self):
        """Layout widgets"""

        self.refresh_button.pack(pady=(0, 15))

        self.source_label.pack(anchor=W, pady=(5, 2))
        self.source_combobox.pack(fill=X, pady=(0, 5))

        # Pack source info directly - divider will move slightly but info is always visible
        self.source_info.pack(anchor=W, pady=(0, 10))

        self.separator1.pack(fill=X, pady=10)

        self.target_label.pack(anchor=W, pady=(5, 2))
        self.target_combobox.pack(fill=X, pady=(0, 5))

        # Pack target info directly - ensures visibility
        self.target_info.pack(anchor=W, pady=(0, 5))

        self.warning_label.pack(anchor=W, pady=(0, 10))

    def _refresh_disks(self):
        """Refresh list of available drive letters (SD cards)"""
        try:
            drives = self.disk_manager.list_drive_letters()

            if not drives:
                if self.main_window:
                    if self.main_window.current_mode == "cleanup":
                        self.main_window.show_custom_info(
                            "未找到SD卡",
                            "未检测到可移动驱动器。请插入SD卡并刷新。",
                            width=500,
                            height=200
                        )
                    else:
                        self.main_window.show_custom_info(
                            "未找到SD卡",
                            "未检测到可移动驱动器。请插入SD卡并刷新。",
                            width=500,
                            height=200
                        )
                return

            # Build display names (show drive letter and total disk size)
            drive_names = []
            self.disk_map = {}

            for drive in drives:
                # Show: "H: - VOLUME_NAME (128.0 GB SD Card)"
                volume_name = drive['name'] if drive['name'] != drive['letter'] else "SD 卡"
                name = f"{drive['letter']} - {volume_name} ({drive['size_gb']:.1f} GB)"
                drive_names.append(name)

                # Map to full disk info (with physical drive path)
                self.disk_map[name] = {
                    'letter': drive['letter'],
                    'name': drive['disk_name'],
                    'path': drive['physical_drive'],  # This is the physical drive path like \\.\PhysicalDrive1
                    'index': drive['physical_index'],
                    'size_bytes': drive['size_bytes'],
                    'size_gb': drive['size_gb'],
                    'partition_size_gb': drive['partition_size_gb']
                }

            # Update comboboxes
            self.source_combobox['values'] = drive_names
            self.target_combobox['values'] = drive_names

            # Show notification based on mode
            if self.main_window:
                if self.main_window.current_mode == "cleanup":
                    # In cleanup mode, only need one SD card
                    self.main_window.show_custom_info(
                        "检测到SD卡",
                        f"成功检测到 {len(drives)} 张SD卡。\n\n"
                        f"请从下拉菜单中选择要清理的SD卡。",
                        width=500,
                        height=250
                    )
                else:
                    # In migration mode, need 2 SD cards
                    if len(drives) >= 2:
                        self.main_window.show_custom_info(
                            "检测到SD卡",
                            f"成功检测到 {len(drives)} 张SD卡。\n\n"
                            f"请从下拉菜单中选择源驱动器和目标驱动器。",
                            width=500,
                            height=250
                        )
                    elif len(drives) == 1:
                        self.main_window.show_custom_info(
                            "SD卡数量不足",
                            f"仅检测到 {len(drives)} 张SD卡。\n\n"
                            f"迁移模式需要两张已挂载的SD卡:\n"
                            f"• 源SD卡 (较小容量)\n"
                            f"• 目标SD卡 (较大容量)\n\n"
                            f"请插入另一张SD卡并刷新。",
                            width=550,
                            height=330
                        )

        except Exception as e:
            if self.main_window:
                self.main_window.show_custom_info(
                    "错误",
                    f"列出驱动器失败:\n\n{str(e)}",
                    width=500,
                    height=250
                )

    def _on_source_selected(self, event):
        """Called when source disk is selected"""
        selection = self.source_combobox.get()
        if not selection:
            return

        disk = self.disk_map[selection]
        self.source_disk = disk

        # Update info label
        info = f"驱动器: {disk['letter']}\n"
        info += f"物理路径: {disk['path']}\n"
        info += f"总容量: {disk['size_gb']:.2f} GB"
        self.source_info.config(text=info)

        # Notify callback
        if self.on_source_selected:
            self.on_source_selected(disk)

    def _on_target_selected(self, event):
        """Called when target disk is selected"""
        selection = self.target_combobox.get()
        if not selection:
            return

        disk = self.disk_map[selection]

        # Prevent selecting same disk as source
        if self.source_disk and disk['path'] == self.source_disk['path']:
            if self.main_window:
                self.main_window.show_custom_info(
                    "无效选择",
                    "目标磁盘不能与源磁盘相同!",
                    width=500,
                    height=200
                )
            self.target_combobox.set('')
            return

        self.target_disk = disk

        # Update info label
        info = f"驱动器: {disk['letter']}\n"
        info += f"物理路径: {disk['path']}\n"
        info += f"总容量: {disk['size_gb']:.2f} GB"
        self.target_info.config(text=info)

        # Notify callback
        if self.on_target_selected:
            self.on_target_selected(disk)

    def clear_target(self):
        """Clear target selection"""
        self.target_combobox.set('')
        self.target_disk = None
        self.target_info.config(text="未选择\n\n")  # Keep 3 lines to maintain spacing

    def show_target_selector(self):
        """Show target disk selector widgets (for migration mode)"""
        self.separator1.pack(fill=X, pady=10)
        self.target_label.pack(anchor=W, pady=(5, 2))
        self.target_combobox.pack(fill=X, pady=(0, 5))
        self.target_info.pack(anchor=W, pady=(0, 5))
        self.warning_label.pack(anchor=W, pady=(0, 10))

    def hide_target_selector(self):
        """Hide target disk selector widgets (for cleanup mode)"""
        self.separator1.pack_forget()
        self.target_label.pack_forget()
        self.target_combobox.pack_forget()
        self.target_info.pack_forget()
        self.warning_label.pack_forget()

    def clear_selections(self):
        """Clear both source and target selections"""
        self.source_combobox.set('')
        self.source_disk = None
        self.source_info.config(text="未选择\n\n")
        self.clear_target()

    def set_enabled(self, enabled):
        """Enable/disable disk selection"""
        state = "readonly" if enabled else DISABLED
        self.source_combobox.config(state=state)
        self.target_combobox.config(state=state)

        button_state = NORMAL if enabled else DISABLED
        self.refresh_button.config(state=button_state)
