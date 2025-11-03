"""
Main GUI Window for SD Card Migrator
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
from tkinter import messagebox
import webbrowser
import os
import subprocess
import sys
import json
import logging

from gui.disk_selector import DiskSelectorFrame
from gui.partition_viewer import PartitionViewerFrame
from gui.migration_options import MigrationOptionsFrame
from gui.progress_panel import ProgressPanel
from gui.log_panel import LogPanel
from core.disk_manager import DiskManager
from core.partition_scanner import PartitionScanner
from core.migration_engine import MigrationEngine
from core.cleanup_engine import CleanupEngine

class MainWindow:
    """Main application window"""

    def __init__(self, root):
        self.root = root
        self.disk_manager = DiskManager()
        self.scanner = PartitionScanner()
        self.migration_engine = None

        # State
        self.current_mode = "migration"  # "migration" or "cleanup"
        self.source_disk = None
        self.target_disk = None
        self.source_layout = None
        self.target_layout = None
        self.migration_options = {
            'migrate_fat32': True,
            'migrate_linux': True,
            'migrate_android': True,
            'migrate_emummc': True,
            'expand_fat32': True
        }
        self.cleanup_options = {
            'remove_linux': False,
            'remove_android': False,
            'remove_emummc': False,
            'expand_fat32': True
        }

        # Build UI
        self._create_menu()
        self._create_widgets()
        self._layout_widgets()

        # Bind keyboard shortcut for log toggle (Ctrl+L)
        self.root.bind('<Control-l>', lambda e: self._toggle_log_panel())

        # Load preferences and restore log panel state
        self._load_log_preference()

    def _create_menu(self):
        """Create menu bar"""
        menubar = ttk.Menu(self.root)
        self.root.config(menu=menubar)

        # Help Menu
        help_menu = ttk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用指南", command=self._show_usage_guide)
        help_menu.add_command(label="故障排除", command=self._show_troubleshooting)
        help_menu.add_separator()
        help_menu.add_command(label="查看日志", command=self._open_logs)
        help_menu.add_command(label="在GitHub上报告问题", command=self._open_github_issues)
        help_menu.add_separator()
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        """Create all GUI widgets"""

        # ===== Header =====
        self.header_frame = ttk.Frame(self.root, bootstyle=PRIMARY)

        self.title_label = ttk.Label(
            self.header_frame,
            text="⚙️ NX 迁移专家",
            font=("Segoe UI", 20, "bold"),
            bootstyle="inverse-primary"
        )

        self.subtitle_label = ttk.Label(
            self.header_frame,
            text="任天堂Switch SD卡专业分区管理工具 • 迁移 • 清理 • FAT32 • Linux • Android • emuMMC",
            font=("Segoe UI", 10),
            bootstyle="inverse-primary"
        )

        # ===== Mode Selector =====
        self.mode_frame = ttk.Frame(self.root)

        ttk.Label(
            self.mode_frame,
            text="模式:",
            font=("Segoe UI", 11, "bold")
        ).pack(side=LEFT, padx=(10, 5))

        self.migration_mode_btn = ttk.Button(
            self.mode_frame,
            text="🔄 迁移模式",
            command=lambda: self._switch_mode("migration"),
            bootstyle="primary",
            width=20
        )
        self.migration_mode_btn.pack(side=LEFT, padx=5)

        self.cleanup_mode_btn = ttk.Button(
            self.mode_frame,
            text="🧹 清理模式",
            command=lambda: self._switch_mode("cleanup"),
            bootstyle="secondary-outline",
            width=20
        )
        self.cleanup_mode_btn.pack(side=LEFT, padx=5)

        ttk.Label(
            self.mode_frame,
            text="迁移: 从小容量SD卡复制到大容量SD卡  |  清理: 从单个SD卡移除分区",
            font=("Segoe UI", 9),
            foreground="gray"
        ).pack(side=LEFT, padx=20)

        # ===== Main Content Area =====
        self.content_frame = ttk.Frame(self.root)

        # Left Panel - Disk Selection
        self.left_panel = ttk.Labelframe(
            self.content_frame,
            text="步骤1: 选择磁盘",
            bootstyle=INFO,
            padding=10
        )

        self.disk_selector = DiskSelectorFrame(
            self.left_panel,
            self.disk_manager,
            on_source_selected=self._on_source_selected,
            on_target_selected=self._on_target_selected,
            main_window=self
        )

        # Scan button
        self.scan_button = ttk.Button(
            self.left_panel,
            text="🔍 模拟迁移",
            command=self._scan_sd_cards,
            bootstyle=SUCCESS,
            width=30
        )

        # Middle Panel - Partition Information
        self.middle_panel = ttk.Labelframe(
            self.content_frame,
            text="步骤2: 查看分区",
            bootstyle=INFO,
            padding=10
        )

        # Source partition view (no tabs, just direct frames)
        self.source_partition_frame = PartitionViewerFrame(
            self.middle_panel,
            title="📀 源SD卡"
        )

        # Target partition view
        self.target_partition_frame = PartitionViewerFrame(
            self.middle_panel,
            title="💾 目标SD卡 (迁移后)"
        )

        # Right Panel - Migration Options
        self.right_panel = ttk.Labelframe(
            self.content_frame,
            text="步骤3: 迁移选项",
            bootstyle=INFO,
            padding=10
        )

        self.migration_options_frame = MigrationOptionsFrame(
            self.right_panel,
            on_options_changed=self._on_options_changed
        )

        # Migration button
        self.migrate_button = ttk.Button(
            self.right_panel,
            text="🚀 开始迁移",
            command=self._start_migration,
            bootstyle=SUCCESS,
            width=30,
            state=DISABLED
        )

        # ===== Bottom Panel - Progress =====
        self.bottom_frame = ttk.Frame(self.root)

        # Progress panel
        self.progress_panel = ProgressPanel(self.bottom_frame)

        # ===== Log Panel =====
        self.log_panel = LogPanel(self.root)

        # ===== Status Bar =====
        self.status_frame = ttk.Frame(self.root, bootstyle=DARK)

        self.status_label = ttk.Label(
            self.status_frame,
            text="就绪。点击'刷新磁盘'，选择源和目标驱动器，然后点击'模拟迁移'。",
            font=("Segoe UI", 9),
            foreground="white",
            bootstyle="inverse-dark"
        )

        # Log toggle button
        self.log_toggle_btn = ttk.Button(
            self.status_frame,
            text="显示日志",
            command=self._toggle_log_panel,
            bootstyle="info-outline",
            width=12
        )

    def _layout_widgets(self):
        """Layout all widgets"""

        # Header
        self.header_frame.pack(fill=X, pady=(0, 5))
        self.title_label.pack(pady=(10, 3))
        self.subtitle_label.pack(pady=(0, 10))

        # Mode selector
        self.mode_frame.pack(fill=X, pady=(5, 5))

        # Content area
        self.content_frame.pack(fill=BOTH, expand=YES, padx=8, pady=3)

        # Three column layout
        self.left_panel.pack(side=LEFT, fill=BOTH, expand=NO, padx=(0, 5))
        self.middle_panel.pack(side=LEFT, fill=BOTH, expand=YES, padx=5)
        self.right_panel.pack(side=LEFT, fill=BOTH, expand=NO, padx=(5, 0))

        # Left panel content
        self.disk_selector.pack(fill=BOTH, expand=YES)
        self.scan_button.pack(pady=(10, 0))

        # Middle panel content - use grid for perfect 50/50 split
        self.middle_panel.grid_rowconfigure(0, weight=1)  # Source gets 50%
        self.middle_panel.grid_rowconfigure(1, weight=0)  # Separator
        self.middle_panel.grid_rowconfigure(2, weight=1)  # Target gets 50%
        self.middle_panel.grid_columnconfigure(0, weight=1)

        self.source_partition_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 2.5))

        # Separator line for visual clarity
        separator = ttk.Separator(self.middle_panel, orient='horizontal')
        separator.grid(row=1, column=0, sticky='ew', pady=2.5)

        self.target_partition_frame.grid(row=2, column=0, sticky='nsew', pady=(2.5, 0))

        # Right panel content
        self.migration_options_frame.pack(fill=BOTH, expand=YES)
        self.migrate_button.pack(pady=(10, 0))

        # Bottom panel
        self.bottom_frame.pack(fill=X, padx=8, pady=5)
        self.progress_panel.pack(fill=X)

        # Log panel (initially hidden, will be shown/hidden by toggle)
        # Note: pack() is called in log_panel.show() method

        # Status bar
        self.status_frame.pack(fill=X, side=BOTTOM)
        self.status_label.pack(side=LEFT, pady=5, padx=10)
        self.log_toggle_btn.pack(side=RIGHT, pady=5, padx=10)

    def _switch_mode(self, mode):
        """Switch between migration and cleanup modes"""
        if self.current_mode == mode:
            return  # Already in this mode

        self.current_mode = mode

        # Update button styles
        if mode == "migration":
            self.migration_mode_btn.config(bootstyle="primary")
            self.cleanup_mode_btn.config(bootstyle="secondary-outline")

            # Update UI labels for migration mode
            self.left_panel.config(text="步骤1: 选择源和目标磁盘")
            self.middle_panel.config(text="步骤2: 查看分区")
            self.right_panel.config(text="步骤3: 迁移选项")
            self.scan_button.config(text="🔍 模拟迁移")
            self.migrate_button.config(text="🚀 开始迁移")
            self.source_partition_frame.update_title("📀 源SD卡")
            self.target_partition_frame.update_title("💾 目标SD卡 (迁移后)")
            self._update_status("迁移模式: 选择源和目标SD卡，然后点击'模拟迁移'。")

            # Show target disk selector
            self.disk_selector.show_target_selector()

            # Set options frame to migration mode
            self.migration_options_frame.set_mode("migration")

        else:  # cleanup mode
            self.migration_mode_btn.config(bootstyle="secondary-outline")
            self.cleanup_mode_btn.config(bootstyle="success")

            # Update UI labels for cleanup mode
            self.left_panel.config(text="步骤1: 选择SD卡")
            self.middle_panel.config(text="步骤2: 查看当前分区")
            self.right_panel.config(text="步骤3: 清理选项")
            self.scan_button.config(text="🔍 扫描SD卡")
            self.migrate_button.config(text="🧹 开始清理")
            self.source_partition_frame.update_title("📀 当前SD卡布局")
            self.target_partition_frame.update_title("✨ 清理后 (预览)")
            self._update_status("清理模式: 选择要清理不需要分区的SD卡。")

            # Hide target disk selector in cleanup mode
            self.disk_selector.hide_target_selector()

            # Set options frame to cleanup mode
            self.migration_options_frame.set_mode("cleanup")

        # Reset state
        self.source_disk = None
        self.target_disk = None
        self.source_layout = None
        self.target_layout = None
        self.source_partition_frame.clear()
        self.target_partition_frame.clear()
        self.migrate_button.config(state=DISABLED)
        self.disk_selector.clear_selections()

        # Reset progress panel with current mode
        self.progress_panel.reset(mode)

    def _on_source_selected(self, disk_info):
        """Called when source disk is selected"""
        self.source_disk = disk_info
        self.source_layout = None
        self.source_partition_frame.clear()
        self.target_partition_frame.clear()
        self.migrate_button.config(state=DISABLED)

        self._update_status(f"Source selected: {disk_info['letter']} - {disk_info['name']} ({disk_info['size_gb']:.1f} GB)")

    def _on_target_selected(self, disk_info):
        """Called when target disk is selected"""
        self.target_disk = disk_info
        self.target_layout = None
        self.target_partition_frame.clear()
        self.migrate_button.config(state=DISABLED)

        # Validate target is larger than source
        if self.source_disk and disk_info['size_bytes'] <= self.source_disk['size_bytes']:
            self.show_custom_info(
                "无效目标",
                f"目标磁盘 ({disk_info['letter']}, {disk_info['size_gb']:.1f} GB) 必须大于源磁盘 ({self.source_disk['letter']}, {self.source_disk['size_gb']:.1f} GB)",
                width=500,
                height=200
            )
            self.disk_selector.clear_target()
            self.target_disk = None
            return

        self._update_status(f"Target selected: {disk_info['letter']} - {disk_info['name']} ({disk_info['size_gb']:.1f} GB)")

    def _on_options_changed(self, options):
        """Called when migration/cleanup options change"""
        if self.current_mode == "migration":
            self.migration_options = options
        else:  # cleanup mode
            # Convert options to cleanup options format
            # In cleanup mode, checked = remove
            self.cleanup_options = {
                'remove_linux': options['migrate_linux'],  # Note: inverted meaning
                'remove_android': options['migrate_android'],
                'remove_emummc': options['migrate_emummc'],
                'expand_fat32': options['expand_fat32']
            }

        # Recalculate layout if we already have source layout
        if self.current_mode == "migration":
            if self.source_layout and self.target_disk:
                self._calculate_layout()
        else:  # cleanup mode
            if self.source_layout:
                self._calculate_layout()

    def _scan_sd_cards(self):
        """Scan SD card and simulate layout (works for both migration and cleanup modes)"""
        if not self.source_disk:
            self.show_custom_info("未选择磁盘", "请先选择一个SD卡。", width=450, height=200)
            return

        # In migration mode, require target disk
        if self.current_mode == "migration":
            if not self.target_disk:
                self.show_custom_info("未选择目标磁盘", "请选择源和目标SD卡。", width=450, height=200)
                return

        if self.current_mode == "migration":
            self._update_status("正在扫描源磁盘并模拟迁移...")
            self.scan_button.config(state=DISABLED, text="⏳ 模拟中...")
        else:  # cleanup mode
            self._update_status("正在扫描SD卡并模拟清理...")
            self.scan_button.config(state=DISABLED, text="⏳ 扫描中...")

        # Run scan in thread to avoid blocking UI
        def scan_thread():
            try:
                # Scan source disk
                source_layout = self.scanner.scan_disk(self.source_disk['path'])

                # Update UI in main thread
                self.root.after(0, self._on_scan_complete, source_layout, None)

            except Exception as e:
                self.root.after(0, self._on_scan_error, str(e))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _on_scan_complete(self, source_layout, target_layout=None):
        """Called when disk scan completes"""
        self.source_layout = source_layout

        # Update button text based on mode
        if self.current_mode == "migration":
            self.scan_button.config(state=NORMAL, text="🔍 模拟迁移")
        else:
            self.scan_button.config(state=NORMAL, text="🔍 扫描SD卡")

        # Display source partition information
        self.source_partition_frame.display_layout(source_layout, self.source_disk)

        # Update available toggles based on what partitions exist on the source SD card
        # This applies to both migration and cleanup modes
        self.migration_options_frame.update_available_partitions(
            has_linux=source_layout.has_linux,
            has_android=source_layout.has_android,
            has_emummc=source_layout.has_emummc
        )

        # Sync the options from the frame to ensure we use the correct state
        if self.current_mode == "migration":
            self.migration_options = self.migration_options_frame.options.copy()
        else:
            # Convert to cleanup options format
            options = self.migration_options_frame.options
            self.cleanup_options = {
                'remove_linux': options['migrate_linux'],
                'remove_android': options['migrate_android'],
                'remove_emummc': options['migrate_emummc'],
                'expand_fat32': options['expand_fat32']
            }

        # Update status
        summary = source_layout.get_summary()

        if self.current_mode == "migration":
            self._update_status(f"扫描完成: {summary}。正在计算目标布局...")
        else:
            self._update_status(f"扫描完成: {summary}。选择清理选项并计算预览...")

        # Automatically calculate and display the simulated target layout
        self._calculate_layout()

    def _on_scan_error(self, error_msg):
        """Called when disk scan fails"""
        self.scan_button.config(state=NORMAL, text="🔍 模拟迁移")

        self.show_custom_info(
            "扫描失败",
            f"磁盘扫描失败:\n\n{error_msg}",
            width=500,
            height=250
        )

        self._update_status("扫描失败。请重试。")

    def _calculate_layout(self):
        """Calculate new partition layout (for both migration and cleanup modes)"""
        if not self.source_layout:
            self.show_custom_info(
                "缺少信息",
                "请先扫描 SD 卡。",
                width=500,
                height=200
            )
            return

        # In migration mode, require target disk
        if self.current_mode == "migration" and not self.target_disk:
            self.show_custom_info(
                "缺少信息",
                "请先选择目标磁盘。",
                width=500,
                height=200
            )
            return

        try:
            self._update_status("正在计算新分区布局...")

            if self.current_mode == "migration":
                # Migration mode: calculate layout for target disk
                new_layout = self.scanner.calculate_target_layout(
                    self.source_layout,
                    self.target_disk['size_bytes'],
                    self.migration_options
                )

                self.target_layout = new_layout

                # Display new layout
                self.target_partition_frame.display_layout(new_layout, self.target_disk)

            else:  # cleanup mode
                # Cleanup mode: calculate layout for same disk (with partitions removed)
                # Use cleanup options to determine what to remove
                cleanup_options_for_calc = {
                    'migrate_fat32': True,  # Always keep FAT32
                    'migrate_linux': not self.cleanup_options['remove_linux'],
                    'migrate_android': not self.cleanup_options['remove_android'],
                    'migrate_emummc': not self.cleanup_options['remove_emummc'],
                    'expand_fat32': self.cleanup_options['expand_fat32']
                }

                new_layout = self.scanner.calculate_target_layout(
                    self.source_layout,
                    self.source_disk['size_bytes'],  # Same disk size
                    cleanup_options_for_calc
                )

                self.target_layout = new_layout

                # Display new layout (use source disk info since it's the same disk)
                self.target_partition_frame.display_layout(new_layout, self.source_disk)

            # Show comparison
            self._show_layout_comparison()

            # Enable action button
            self.migrate_button.config(state=NORMAL)

            if self.current_mode == "migration":
                self._update_status("布局计算完成。准备开始迁移。")
            else:
                self._update_status("清理预览准备完成。准备开始清理。")

        except Exception as e:
            self.show_custom_info(
                "计算失败",
                f"计算新布局失败：\n\n{str(e)}",
                width=500,
                height=250
            )
            self._update_status("布局计算失败。")

    def _show_layout_comparison(self):
        """Show comparison between source and target layouts"""
        if not self.source_layout or not self.target_layout:
            return

        # Build comparison message based on mode
        if self.current_mode == "migration":
            msg = "迁移摘要：\n\n"

            # FAT32
            if self.migration_options['migrate_fat32']:
                src_fat = self.source_layout.get_fat32_size_mb()
                dst_fat = self.target_layout.get_fat32_size_mb()
                fat32_gain = dst_fat - src_fat
                if self.migration_options['expand_fat32']:
                    msg += f"✓ FAT32: {src_fat:,} MB → {dst_fat:,} MB (+{fat32_gain:,} MB 扩展)\n"
                else:
                    msg += f"✓ FAT32: {src_fat:,} MB → {dst_fat:,} MB (无扩展)\n"

            # Linux
            if self.source_layout.has_linux and self.migration_options['migrate_linux']:
                linux_size = self.source_layout.get_linux_size_mb()
                msg += f"✓ Linux: {linux_size:,} MB (preserved)\n"

            # Android
            if self.source_layout.has_android and self.migration_options['migrate_android']:
                android_size = self.source_layout.get_android_size_mb()
                android_type = "动态" if self.source_layout.android_dynamic else "传统"
                msg += f"✓ Android ({android_type}): {android_size:,} MB (保持)\n"

            # emuMMC
            if self.source_layout.has_emummc and self.migration_options['migrate_emummc']:
                emummc_size = self.source_layout.get_emummc_size_mb()
                emummc_type = "双虚拟系统" if self.source_layout.emummc_double else "单虚拟系统"
                msg += f"✓ emuMMC ({emummc_type}): {emummc_size:,} MB (保持)\n"

            msg += f"\n源磁盘：{self.source_disk['size_gb']:.1f} GB\n"
            msg += f"目标磁盘：{self.target_disk['size_gb']:.1f} GB"

            self.show_custom_info("布局对比", msg, width=550, height=400)

        else:  # cleanup mode
            msg = "Cleanup Summary:\n\n"

            # FAT32
            src_fat = self.source_layout.get_fat32_size_mb()
            dst_fat = self.target_layout.get_fat32_size_mb()
            fat32_gain = dst_fat - src_fat
            if self.cleanup_options['expand_fat32']:
                msg += f"✓ FAT32: {src_fat:,} MB → {dst_fat:,} MB (+{fat32_gain:,} MB 回收)\n"
            else:
                msg += f"✓ FAT32: {src_fat:,} MB (无扩展)\n"

            # Linux
            if self.source_layout.has_linux:
                linux_size = self.source_layout.get_linux_size_mb()
                if self.cleanup_options['remove_linux']:
                    msg += f"✗ Linux: {linux_size:,} MB (will be REMOVED)\n"
                else:
                    msg += f"✓ Linux: {linux_size:,} MB (preserved)\n"

            # Android
            if self.source_layout.has_android:
                android_size = self.source_layout.get_android_size_mb()
                android_type = "动态" if self.source_layout.android_dynamic else "传统"
                if self.cleanup_options['remove_android']:
                    msg += f"✗ Android ({android_type}): {android_size:,} MB (将被删除)\n"
                else:
                    msg += f"✓ Android ({android_type}): {android_size:,} MB (保持)\n"

            # emuMMC
            if self.source_layout.has_emummc:
                emummc_size = self.source_layout.get_emummc_size_mb()
                emummc_type = "双虚拟系统" if self.source_layout.emummc_double else "单虚拟系统"
                if self.cleanup_options['remove_emummc']:
                    msg += f"✗ emuMMC ({emummc_type}): {emummc_size:,} MB (将被删除)\n"
                else:
                    msg += f"✓ emuMMC ({emummc_type}): {emummc_size:,} MB (保持)\n"

            msg += f"\nSD 卡：{self.source_disk['size_gb']:.1f} GB"

            self.show_custom_info("清理摘要", msg, width=550, height=380)

    def _start_migration(self):
        """Start the migration or cleanup process (depending on mode)"""

        if self.current_mode == "migration":
            # Migration mode confirmations
            response = self.show_custom_confirm(
                "确认迁移",
                f"⚠️ 警告 ⚠️\n\n"
                f"这将会清除目标磁盘上的所有数据：\n"
                f"{self.target_disk['letter']} - {self.target_disk['name']} ({self.target_disk['size_gb']:.1f} GB)\n\n"
                f"源磁盘 ({self.source_disk['letter']}) 不会被修改。\n\n"
                f"您确定要继续吗？",
                yes_text="是的，继续",
                no_text="取消",
                style="warning",
                width=550,
                height=400
            )

            if not response:
                return

            # Double confirmation
            response2 = self.show_custom_confirm(
                "最终确认",
                f"⚠️ 最后警告 ⚠️\n\n"
                f"{self.target_disk['letter']} ({self.target_disk['name']}) 上的所有数据将被永久清除。\n\n"
                f"此操作无法撤销！",
                yes_text="是的，清除并迁移",
                no_text="取消",
                style="danger",
                width=550,
                height=330
            )

            if not response2:
                return

            # Enable file logging for this operation
            from main import enable_file_logging
            log_file = enable_file_logging()
            logging.getLogger(__name__).info(f"Migration operation started - logging to {log_file}")

            # Disable UI during migration
            self._set_ui_enabled(False)

            # Create migration engine
            self.migration_engine = MigrationEngine(
                self.source_disk,
                self.target_disk,
                self.source_layout,
                self.target_layout,
                self.migration_options
            )

            # Connect progress callbacks
            self.migration_engine.on_progress = self._on_operation_progress
            self.migration_engine.on_complete = self._on_operation_complete
            self.migration_engine.on_error = self._on_operation_error

            # Start migration in thread
            self._update_status("迁移进行中...")
            self.progress_panel.start()

            threading.Thread(
                target=self.migration_engine.run,
                daemon=True
            ).start()

        else:  # cleanup mode
            # Cleanup mode confirmations
            removed_parts = []
            if self.cleanup_options['remove_linux'] and self.source_layout.has_linux:
                removed_parts.append("Linux partition")
            if self.cleanup_options['remove_android'] and self.source_layout.has_android:
                removed_parts.append("Android partitions")
            if self.cleanup_options['remove_emummc'] and self.source_layout.has_emummc:
                removed_parts.append("emuMMC partition(s)")

            if removed_parts:
                parts_str = ", ".join(removed_parts)
            else:
                parts_str = "No partitions will be removed (only FAT32 expansion)"

            response = self.show_custom_confirm(
                "Confirm Cleanup",
                f"⚠️ WARNING ⚠️\n\n"
                f"This will MODIFY the disk:\n"
                f"{self.source_disk['letter']} - {self.source_disk['name']} ({self.source_disk['size_gb']:.1f} GB)\n\n"
                f"Partitions to remove:\n{parts_str}\n\n"
                f"FAT32 data will be backed up temporarily, then restored.\n\n"
                f"⚠️ IMPORTANT: Make sure you have a backup of your SD card!\n\n"
                f"Are you sure you want to continue?",
                yes_text="Yes, Continue",
                no_text="Cancel",
                style="warning",
                width=600,
                height=500
            )

            if not response:
                return

            # Double confirmation
            response2 = self.show_custom_confirm(
                "最终确认",
                f"⚠️ 最后警告 ⚠️\n\n"
                f"磁盘 {self.source_disk['letter']} 将被修改。\n"
                f"删除的分区将被永久删除。\n\n"
                f"此操作无法撤销！\n\n"
                f"您是否已有备份？",
                yes_text="是的，我已备份 - 继续",
                no_text="取消",
                style="danger",
                width=550,
                height=400
            )

            if not response2:
                return

            # Enable file logging for this operation
            from main import enable_file_logging
            log_file = enable_file_logging()
            logging.getLogger(__name__).info(f"Cleanup operation started - logging to {log_file}")

            # Disable UI during cleanup
            self._set_ui_enabled(False)

            # Create cleanup engine
            self.cleanup_engine = CleanupEngine(
                self.source_disk,
                self.source_layout,
                self.target_layout,
                self.cleanup_options
            )

            # Connect progress callbacks
            self.cleanup_engine.on_progress = self._on_operation_progress
            self.cleanup_engine.on_complete = self._on_operation_complete
            self.cleanup_engine.on_error = self._on_operation_error

            # Start cleanup in thread
            self._update_status("清理进行中...")
            self.progress_panel.start()

            threading.Thread(
                target=self.cleanup_engine.run,
                daemon=True
            ).start()

    def _on_operation_progress(self, stage, percent, message):
        """Called during operation progress (migration or cleanup)"""
        # Show stage and percent in progress panel (top)
        self.root.after(0, self.progress_panel.update, stage, percent)
        # Show detailed message in status bar (bottom)
        status_message = f"{stage} - {message}"
        self.root.after(0, self._update_status, status_message)

    def _on_operation_complete(self):
        """Called when operation completes successfully (migration or cleanup)"""
        def complete_ui():
            self.progress_panel.complete()
            self._set_ui_enabled(True)

            if self.current_mode == "migration":
                self._update_status("迁移成功完成！")
                self.show_custom_info(
                    "迁移完成",
                    "✓ SD 卡迁移成功完成！\n\n"
                    "您现在可以安全地移除两张 SD 卡。",
                    width=500,
                    height=220
                )
            else:  # cleanup mode
                self._update_status("清理成功完成！")
                self.show_custom_info(
                    "清理完成",
                    "✓ SD 卡清理成功完成！\n\n"
                    "不需要的分区已被删除，FAT32 已扩展。\n\n"
                    "您现在可以安全地移除 SD 卡。",
                    width=550,
                    height=300
                )

        self.root.after(0, complete_ui)

    def _on_operation_error(self, error_msg):
        """Called when operation fails (migration or cleanup)"""
        def error_ui():
            self.progress_panel.error()
            self._set_ui_enabled(True)

            if self.current_mode == "migration":
                self._update_status(f"迁移失败：{error_msg}")
                self.show_custom_info(
                    "迁移失败",
                    f"迁移失败，错误信息：\n\n{error_msg}\n\n"
                    f"目标磁盘可能处于不一致状态。",
                    width=550,
                    height=280
                )
            else:  # cleanup mode
                self._update_status(f"清理失败：{error_msg}")
                self.show_custom_info(
                    "清理失败",
                    f"清理失败，错误信息：\n\n{error_msg}\n\n"
                    f"SD 卡可能处于不一致状态。\n"
                    f"如有需要，请从备份恢复。",
                    width=550,
                    height=300
                )

        self.root.after(0, error_ui)

    def _set_ui_enabled(self, enabled):
        """Enable/disable UI during migration"""
        state = NORMAL if enabled else DISABLED

        self.disk_selector.set_enabled(enabled)
        self.scan_button.config(state=state)
        self.migrate_button.config(state=state)
        self.migration_options_frame.set_enabled(enabled)

    def _update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=message)

    def _toggle_log_panel(self):
        """Toggle log panel visibility"""
        self.log_panel.toggle()

        # Update button text
        if self.log_panel.is_visible():
            self.log_toggle_btn.config(text="隐藏日志")
            self._save_log_preference(True)
        else:
            self.log_toggle_btn.config(text="显示日志")
            self._save_log_preference(False)

    def center_window(self, window):
        """Center a popup window on the main window"""
        # This function is now a wrapper to call the actual centering logic
        # after a small delay, preventing the "flicker" effect.
        window.after(10, lambda: self._do_center(window))

    def _do_center(self, window):
        """Actually center the window"""
        # Update both parent and child window to get accurate current positions
        self.root.update_idletasks()
        window.update_idletasks()

        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()

        window_w = window.winfo_width()
        window_h = window.winfo_height()

        x = parent_x + (parent_w // 2) - (window_w // 2)
        y = parent_y + (parent_h // 2) - (window_h // 2)

        window.geometry(f"+{x}+{y}")

    def show_custom_info(self, title, message, parent=None, blocking=True, width=400, height=200):
        """Show a custom centered info dialog"""
        # Scale down for 1080p (cosmetic improvement)
        screen_height = self.root.winfo_screenheight()
        if screen_height < 1440:  # 1080p or lower
            width = int(width * 0.75)
            height = int(height * 0.75)

        parent_window = parent if parent else self.root
        dialog = ttk.Toplevel(parent_window)
        dialog.title(title)
        dialog.transient(parent_window)

        # Withdraw the window to prevent it from appearing at default position
        dialog.withdraw()

        dialog.grab_set()

        info_frame = ttk.Frame(dialog, padding=20)
        info_frame.pack(fill=BOTH, expand=True)

        ttk.Label(info_frame, text=message, wraplength=width-60, justify=CENTER).pack(pady=20)

        ttk.Button(info_frame, text="OK", command=dialog.destroy, bootstyle="primary").pack()

        # Update geometry and calculate centered position
        dialog.update_idletasks()

        # Get parent window position
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_w = parent_window.winfo_width()
        parent_h = parent_window.winfo_height()

        # Calculate centered position
        x = parent_x + (parent_w // 2) - (width // 2)
        y = parent_y + (parent_h // 2) - (height // 2)

        # Set geometry with position
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Now show the window at the correct position
        dialog.deiconify()

        # Force window to front and gain focus (essential for popups from background threads)
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(100, lambda: dialog.attributes('-topmost', False))
        dialog.focus_force()

        if blocking:
            self.root.wait_window(dialog)

    def show_custom_confirm(self, title, message, yes_text="是", no_text="否", style="primary", width=450, height=250):
        """Show a custom centered confirmation dialog that returns True or False."""
        # Scale down for 1080p (cosmetic improvement)
        screen_height = self.root.winfo_screenheight()
        if screen_height < 1440:  # 1080p or lower
            width = int(width * 0.75)
            height = int(height * 0.75)

        dialog = ttk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)

        # Withdraw the window to prevent it from appearing at default position
        dialog.withdraw()

        dialog.grab_set()

        result = [False]  # Use a list to allow modification from inner function

        def on_yes():
            result[0] = True
            dialog.destroy()

        def on_no():
            result[0] = False
            dialog.destroy()

        info_frame = ttk.Frame(dialog, padding=20)
        info_frame.pack(fill=BOTH, expand=True)
        ttk.Label(info_frame, text=message, wraplength=width-60, justify=CENTER).pack(pady=20)

        button_frame = ttk.Frame(info_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text=yes_text, command=on_yes, bootstyle=style).pack(side=LEFT, padx=10)
        ttk.Button(button_frame, text=no_text, command=on_no, bootstyle="secondary").pack(side=LEFT, padx=10)

        # Update geometry and calculate centered position
        dialog.update_idletasks()

        # Get parent window position
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()

        # Calculate centered position
        x = parent_x + (parent_w // 2) - (width // 2)
        y = parent_y + (parent_h // 2) - (height // 2)

        # Set geometry with position
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Now show the window at the correct position
        dialog.deiconify()

        # Force window to front and gain focus
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(100, lambda: dialog.attributes('-topmost', False))
        dialog.focus_force()

        self.root.wait_window(dialog)
        return result[0]

    # ===== Menu Handlers =====

    def _show_usage_guide(self):
        """Show usage guide dialog"""
        usage_text = """使用指南

步骤1: 选择磁盘
• 插入源SD卡(较小)和目标SD卡(较大)
• 点击"刷新磁盘"来检测SD卡
• 选择您的源SD卡(原始卡)
• 选择您的目标SD卡(目标卡)

警告: 目标磁盘将被完全擦除!

步骤2: 扫描源SD卡
• 点击"模拟迁移"
• 等待扫描完成
• 查看检测到的分区布局

工具会自动检测:
• FAT32分区 (hos_data)
• Linux分区 (L4T)
• Android分区 (动态或传统)
• emuMMC分区 (单个或双虚拟系统)

步骤3: 配置迁移
选择要迁移的内容:
• FAT32分区 (默认迁移，自动扩展)
• Linux分区 (可选)
• Android分区 (可选)
• emuMMC分区 (可选)

步骤4: 查看布局
• 查看新的分区布局
• 检查显示大小变化的对比
• 验证FAT32扩展和可用空间

步骤5: 开始迁移
• 点击"开始迁移"
• 确认警告对话框
• 等待迁移完成 (128GB需要30-60分钟)

迁移过程中请勿移除SD卡或关机!

步骤6: 验证
• 安全移除两张SD卡
• 将目标SD卡插入任天堂Switch
• 正常启动 - 所有数据和分区都已保留
"""

        self._show_scrollable_dialog("使用指南", usage_text, width=700, height=650)

    def _show_troubleshooting(self):
        """Show troubleshooting dialog"""
        troubleshooting_text = """故障排除

"需要管理员权限"
• 右键点击可执行文件并选择"以管理员身份运行"
• 直接磁盘访问需要管理员权限

"未找到SD卡"
• 确保SD卡正确插入
• 点击"刷新磁盘"重新扫描
• 尝试不同的USB端口
• 在设备管理器中检查SD卡读卡器
• 确保SD卡未被其他程序挂载/使用
• 联系设备提供方

"目标磁盘必须更大"
• 确保目标SD卡实际上比源卡大
• 某些SD卡报告的大小略有不同
• 尝试容量更大的目标卡

迁移失败
• 检查SD卡连接
• 尝试不同的SD卡读卡器
• 验证目标SD卡是否写保护
• 检查目标SD卡是否有坏扇区
• 关闭所有访问SD卡的程序
• 在SD卡上运行磁盘检查 (chkdsk)

迁移后emuMMC不工作
• 工具会自动更新emuMMC扇区偏移
• 如果问题持续，验证emuMMC/RAW1或emuMMC/RAW2
  文件夹包含正确的偏移
• 检查日志文件中的emuMMC更新错误
• 确保已启用"迁移emuMMC"选项

迁移速度慢
• 使用高质量的SD卡读卡器 (USB 3.0+)
• 避免使用USB拓展坞 - 直接连接到PC
• 尽可能关闭后台程序以释放系统资源
• 检查杀毒软件是否在扫描SD卡

分区布局不正确
• 验证源SD卡设置正确
• 检查日志文件中的分区检测警告
• 尝试重新扫描源磁盘
• 确保最初使用了hekate分区管理器

获取更多帮助:
• 检查日志文件 (NXMigrator_YYYYMMDD_HHMMSS.log)
• 在GitHub上报告问题并附上日志文件
"""

        self._show_scrollable_dialog("故障排除", troubleshooting_text, width=700, height=650)

    def _open_logs(self):
        """Open the most recent log file"""
        try:
            # Find the most recent log file
            log_files = [f for f in os.listdir('.') if f.startswith('nx_migrator_pro_') and f.endswith('.log')]

            if not log_files:
                self.show_custom_info(
                    "未找到日志",
                    "当前目录中未找到日志文件。",
                    width=450,
                    height=200
                )
                return

            # Sort by modification time and get the most recent
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            latest_log = log_files[0]

            # Open with default text editor
            if sys.platform == 'win32':
                os.startfile(latest_log)
            elif sys.platform == 'darwin':
                subprocess.run(['open', latest_log])
            else:
                subprocess.run(['xdg-open', latest_log])

        except Exception as e:
            self.show_custom_info(
                "打开日志错误",
                f"打开日志文件失败：\n\n{str(e)}",
                width=500,
                height=220
            )

    def _open_github_issues(self):
        """Open GitHub issues page"""
        try:
            # Update this URL to your actual GitHub repository
            webbrowser.open('https://github.com/nangongjing1/NX-Migrator-Pro_Mod/issues')
        except Exception as e:
            self.show_custom_info(
                "Error",
                f"Failed to open browser:\n\n{str(e)}",
                width=450,
                height=250
            )

    def _show_about(self):
        """Show about dialog"""
        # Get version from main module
        try:
            import __main__
            version = getattr(__main__, '__version__', '1.0.0')
        except:
            version = '1.0.0'

        about_text = f"""NX MIGRATOR PRO

版本: {version}

任天堂Switch SD卡专业分区管理工具。

功能特性:
• 迁移模式 - 从小容量SD卡迁移分区到大容量SD卡
• 清理模式 - 删除不需要的分区并扩展FAT32
支持格式: FAT32, Linux (L4T), Android, emuMMC

版权所有 (c) 2025 Sthetix
许可证: GPL-2.0

为任天堂Switch自制软件社区制作

---
中文翻译 葡萄糖酸菜鱼;南宫镜
此中文翻译版为非官方版本, 推荐使用官方英文版
https://github.com/sthetix/NX-Migrator-Pro/releases
"""

        self._show_scrollable_dialog("关于 NX Migrator Pro", about_text, width=600, height=530)

    def _show_scrollable_dialog(self, title, content, width=600, height=500):
        """Show a scrollable text dialog"""
        # Scale down for 1080p (cosmetic improvement)
        screen_height = self.root.winfo_screenheight()
        if screen_height < 1440:  # 1080p or lower
            width = int(width * 0.75)
            height = int(height * 0.75)

        dialog = ttk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)

        # Withdraw the window to prevent it from appearing at default position
        dialog.withdraw()

        dialog.grab_set()

        # Create frame for content
        content_frame = ttk.Frame(dialog, padding=10)
        content_frame.pack(fill=BOTH, expand=True)

        # Create text widget with scrollbar
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        text_widget = ttk.Text(
            text_frame,
            wrap='word',
            yscrollcommand=scrollbar.set,
            font=("Consolas", 9),
            padx=10,
            pady=10,
            height=15
        )
        text_widget.pack(side=LEFT, fill=BOTH, expand=False)
        scrollbar.config(command=text_widget.yview)

        # Insert content
        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')

        # Close button
        ttk.Button(
            content_frame,
            text="关闭",
            command=dialog.destroy,
            bootstyle="primary",
            width=15
        ).pack()

        # Update geometry and calculate centered position
        dialog.update_idletasks()

        # Get parent window position
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()

        # Calculate centered position
        x = parent_x + (parent_w // 2) - (width // 2)
        y = parent_y + (parent_h // 2) - (height // 2)

        # Set geometry with position
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Now show the window at the correct position
        dialog.deiconify()

        # Force window to front
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(100, lambda: dialog.attributes('-topmost', False))
        dialog.focus_force()

    def _save_log_preference(self, visible):
        """Save log panel visibility preference"""
        try:
            prefs = {'log_panel_visible': visible}
            with open('.nx_migrator_prefs.json', 'w') as f:
                json.dump(prefs, f)
        except Exception:
            # Silently ignore errors saving preferences
            pass

    def _load_log_preference(self):
        """Load and apply log panel visibility preference"""
        try:
            if os.path.exists('.nx_migrator_prefs.json'):
                with open('.nx_migrator_prefs.json', 'r') as f:
                    prefs = json.load(f)
                    if prefs.get('log_panel_visible', False):
                        self.log_panel.show()
                        self.log_toggle_btn.config(text="隐藏日志")
        except Exception:
            # Silently ignore errors loading preferences
            pass
