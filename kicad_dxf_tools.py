import ezdxf
import pcbnew
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.colorchooser import askcolor
# Add required imports for gap healing
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union, polygonize
from collections import Counter
import traceback  # Add import for stack traces

class SelectableErrorDialog:
    """Error dialog with selectable text for better debugging"""
    def __init__(self, parent, title, message):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)  # Dialog will be modal
        self.dialog.grab_set()
        
        # Calculate dialog size (60% of parent window)
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        width = int(parent_width * 0.6)
        height = int(parent_height * 0.6)
        
        # Center the dialog on the parent
        x = parent.winfo_rootx() + (parent_width - width) // 2
        y = parent.winfo_rooty() + (parent_height - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Error icon
        try:
            icon_label = tk.Label(self.dialog, text="❌", font=("Arial", 24))
            icon_label.pack(pady=(10, 0))
        except:
            # Fallback if emoji not supported
            icon_label = tk.Label(self.dialog, text="ERROR", font=("Arial", 16, "bold"))
            icon_label.pack(pady=(10, 0))
        
        # Frame containing text widget and scrollbars
        frame = ttk.Frame(self.dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add text widget with scrollbars
        text = tk.Text(frame, wrap=tk.WORD)
        
        # Vertical scrollbar
        vsb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        
        # Horizontal scrollbar
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(xscrollcommand=hsb.set)
        
        # Grid layout
        text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights for proper resize
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        # Insert error message
        text.insert("1.0", message)
        text.configure(state="disabled", bg="white")  # Read-only but selectable
        
        # Close button
        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=10)
        
        # Set focus to the dialog
        self.dialog.focus_set()
        
        # Make the dialog resizable
        self.dialog.resizable(True, True)
        
        # Wait for the window to be destroyed
        parent.wait_window(self.dialog)

class SelectableMessageDialog(SelectableErrorDialog):
    """Generic dialog with selectable text for any message type (warning, info, etc.)"""
    def __init__(self, parent, title, message, icon_text="ℹ️"):
        # Use the SelectableErrorDialog as base but override the icon
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)  # Dialog will be modal
        self.dialog.grab_set()
        
        # Calculate dialog size (60% of parent window)
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        width = int(parent_width * 0.6)
        height = int(parent_height * 0.6)
        
        # Center the dialog on the parent
        x = parent.winfo_rootx() + (parent_width - width) // 2
        y = parent.winfo_rooty() + (parent_height - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Custom icon based on message type
        try:
            icon_label = tk.Label(self.dialog, text=icon_text, font=("Arial", 24))
            icon_label.pack(pady=(10, 0))
        except:
            # Fallback if emoji not supported
            icon_label = tk.Label(self.dialog, text=title.upper(), font=("Arial", 16, "bold"))
            icon_label.pack(pady=(10, 0))
        
        # Frame containing text widget and scrollbars
        frame = ttk.Frame(self.dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add text widget with scrollbars
        text = tk.Text(frame, wrap=tk.WORD)
        
        # Vertical scrollbar
        vsb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        
        # Horizontal scrollbar
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(xscrollcommand=hsb.set)
        
        # Grid layout
        text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights for proper resize
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        # Insert message
        text.insert("1.0", message)
        text.configure(state="disabled", bg="white")  # Read-only but selectable
        
        # Close button
        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=10)
        
        # Set focus to the dialog
        self.dialog.focus_set()
        
        # Make the dialog resizable
        self.dialog.resizable(True, True)
        
        # Wait for the window to be destroyed
        parent.wait_window(self.dialog)

class KicadDxfApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KiCad DXF Tool")
        
        # Add Escape key binding to close the application
        self.root.bind("<Escape>", self.exit_application)
        
        # Get screen dimensions
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Calculate window size (80% of screen)
        window_width = int(screen_width * 0.8)
        window_height = int(screen_height * 0.8)
        
        # Calculate position to center the window
        position_x = int((screen_width - window_width) / 2)
        position_y = int((screen_height - window_height) / 2)
        
        # Set window size and position
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        
        self.board_file = ""
        self.dxf_file = ""
        self.net_name = ""  # Initialize with empty net name
        self.board = None
        self.net_names = []  # Store list of available nets
        
        self.entities = []
        self.selected_entities = {}  # entity -> is_outer_boundary (True/False)
        
        # Add new data structures for line mode
        self.segment_entities = {}   # canvas_id -> (entity, segment_index)
        self.selected_segments = {}  # (entity, segment_index) -> True
        
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.canvas_entities = {}
        
        # Add this line to define boundary_type_var
        self.boundary_type_var = tk.StringVar(value="outer")
        
        # Add variables for gap healing - change default to True
        self.heal_gaps = tk.BooleanVar(value=True)  # Changed from False to True
        self.gap_tolerance = tk.DoubleVar(value=0.001)
        self.segments = []
        
        # Add mode selection variable
        self.app_mode = tk.StringVar(value="zone")  # Default to zone mode
        
        # Add track width configuration
        self.track_width = tk.DoubleVar(value=0.2)  # Default 0.2mm width
        
        # Add variables for selection box (rubber band selection)
        self.rubber_band_active = False
        self.rubber_band_start = None
        self.rubber_band_end = None
        self.rubber_band_id = None
        self.mouse_position = (0, 0)  # Track mouse position for tooltips
        
        self.create_ui()
    
    def create_ui(self):
        # Create main layout frames
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.bottom_frame = ttk.Frame(self.root)
        self.bottom_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # File selection controls in top frame
        ttk.Label(self.top_frame, text="Board File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.board_file_var = tk.StringVar()
        ttk.Entry(self.top_frame, textvariable=self.board_file_var, width=40).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.top_frame, text="Browse...", command=self.select_board_file).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(self.top_frame, text="DXF File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.dxf_file_var = tk.StringVar()
        ttk.Entry(self.top_frame, textvariable=self.dxf_file_var, width=40).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(self.top_frame, text="Browse...", command=self.select_dxf_file).grid(row=1, column=2, padx=5, pady=5)
        # Removed the "Load DXF" button since files will now auto-load
        
        # Net selection dropdown - with improved styling and empty initial state
        ttk.Label(self.top_frame, text="Net Name:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.net_name_var = tk.StringVar()  # Initialize with no default value
        
        # Create a style for the combobox that looks less "disabled"
        style = ttk.Style()
        style.map('TCombobox',
                 fieldbackground=[('readonly', 'white')],
                 selectbackground=[('readonly', '#0078d7')],
                 selectforeground=[('readonly', 'white')])
        
        self.net_dropdown = ttk.Combobox(
            self.top_frame,
            textvariable=self.net_name_var,
            width=38,
            state="readonly"
        )
        self.net_dropdown.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        self.net_dropdown['values'] = ["No board loaded"]  # Default placeholder
        self.net_dropdown.set("No board loaded")  # Set initial text
        
        # Disable the dropdown until a board is loaded
        self.net_dropdown.configure(state="disabled")
        
        # Add gap healing options to top frame
        ttk.Label(self.top_frame, text="Gap Healing:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(self.top_frame, text="Heal gaps", variable=self.heal_gaps).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Add tolerance input
        ttk.Label(self.top_frame, text="Tolerance:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.top_frame, textvariable=self.gap_tolerance, width=10).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Add mode selection
        ttk.Label(self.top_frame, text="Mode:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(self.top_frame, text="Zone Mode", variable=self.app_mode, 
                      value="zone", command=self.update_mode_ui).grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(self.top_frame, text="Line Mode", variable=self.app_mode, 
                      value="line", command=self.update_mode_ui).grid(row=5, column=2, sticky=tk.W, padx=5, pady=5)
        
        # Add track width control (only visible in line mode)
        self.track_width_frame = ttk.Frame(self.top_frame)
        self.track_width_frame.grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Label(self.track_width_frame, text="Track Width (mm):").pack(side=tk.LEFT)
        ttk.Entry(self.track_width_frame, textvariable=self.track_width, width=8).pack(side=tk.LEFT, padx=5)
        
        # Create a new frame for zone type (Filled/Keepout) for zone mode
        self.zone_type_frame = ttk.Frame(self.top_frame)
        self.zone_type_frame.grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(self.zone_type_frame, text="Filled zone", variable=self.boundary_type_var, value="outer").pack(side=tk.LEFT)
        ttk.Radiobutton(self.zone_type_frame, text="Keepout zone", variable=self.boundary_type_var, value="inner").pack(side=tk.LEFT)
        
        # Initially, since default mode is zone, show zone_type_frame and hide track_width_frame
        self.track_width_frame.grid_remove()
        
        # Canvas in main frame
        self.canvas_frame = ttk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Update canvas bindings to include rubber band selection
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows and MacOS
        self.canvas.bind("<Button-4>", lambda e: self.on_mouse_wheel(e, 1))  # Linux scroll up
        self.canvas.bind("<Button-5>", lambda e: self.on_mouse_wheel(e, -1))  # Linux scroll down
        self.canvas.bind("<ButtonPress-2>", self.start_pan)  # Middle button for panning
        self.canvas.bind("<B2-Motion>", self.pan_canvas)
        self.canvas.bind("<Motion>", self.on_canvas_motion)  # Track mouse position
        
        # Selection panel in main frame - increase width from 300 to 400
        self.selection_frame = ttk.Frame(self.main_frame, width=400)
        self.selection_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        ttk.Label(self.selection_frame, text="Selected Entities:").pack(anchor=tk.W)
        
        # Create a frame for the treeview and scrollbars
        tree_frame = ttk.Frame(self.selection_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create vertical scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create horizontal scrollbar
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create and configure treeview with scrollbars
        self.selection_list = ttk.Treeview(
            tree_frame, 
            columns=("Type", "Zone Type"),
            show="headings",
            height=10,  # Set minimum height in rows
            selectmode="browse",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        self.selection_list.pack(fill=tk.BOTH, expand=True)
        
        # Configure scrollbars to work with treeview
        vsb.config(command=self.selection_list.yview)
        hsb.config(command=self.selection_list.xview)
        
        # Configure treeview columns - increase Zone Type column width
        self.selection_list.heading("Type", text="Type")
        self.selection_list.heading("Zone Type", text="Zone Type")
        self.selection_list.column("Type", width=250, minwidth=200, stretch=True)
        self.selection_list.column("Zone Type", width=200, minwidth=150, stretch=True)
        
        # Configure row height based on font size
        default_font = tkfont.nametofont("TkDefaultFont")
        font_height = default_font.metrics("linespace")
        row_padding = 2
        row_height = font_height + row_padding
        
        style = ttk.Style()
        style.configure("Treeview", rowheight=row_height)
        
        # Print info about the calculated height for debugging
        print(f"Font height: {font_height}, Row height set to: {row_height}")

        ttk.Button(self.selection_frame, text="Change Type", command=self.change_entity_type).pack(pady=5, fill=tk.X)
        ttk.Button(self.selection_frame, text="Remove Selection", command=self.remove_selection).pack(pady=5, fill=tk.X)
        
        # Add right-click context menu to the treeview
        self.context_menu = tk.Menu(self.selection_list, tearoff=0)
        self.context_menu.add_command(label="Remove", command=self.remove_selection)
        
        # Bind right-click to show context menu
        self.selection_list.bind("<Button-3>", self.show_context_menu)
        
        # Bind selection event to highlight the entity in the drawing
        self.selection_list.bind("<<TreeviewSelect>>", self.highlight_selected_entity)
        
        # Add keyboard shortcuts for removing items
        self.selection_list.bind("<Delete>", lambda e: self.remove_selection())
        self.selection_list.bind("<BackSpace>", lambda e: self.remove_selection())
        
        # Bottom controls
        ttk.Button(self.bottom_frame, text="Exit", command=self.exit_application).pack(side=tk.RIGHT, padx=5, pady=5)
        ttk.Button(self.bottom_frame, text="Save", command=self.process_and_save).pack(side=tk.RIGHT, padx=5, pady=5)
        ttk.Button(self.bottom_frame, text="Save As...", command=self.process_and_save_as).pack(side=tk.RIGHT, padx=5, pady=5)
        ttk.Button(self.bottom_frame, text="Reset View", command=self.reset_view).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Initialize UI based on mode
        self.update_mode_ui()
    
    def update_mode_ui(self):
        """Update UI elements based on selected mode"""
        # Store previous mode to detect changes
        previous_mode = getattr(self, '_previous_mode', None)
        current_mode = self.app_mode.get()
        
        # Clear selections when switching between modes
        if previous_mode is not None and previous_mode != current_mode:
            self.selected_entities = {}
            self.selected_segments = {}  # Clear selected segments too
            self.update_entity_appearance()
            self.update_selection_list()
        
        # Remember the current mode for next time
        self._previous_mode = current_mode
        
        # Redraw entities to update visualization for the new mode
        if previous_mode is not None and previous_mode != current_mode:
            self.redraw_entities()
        
        if current_mode == "zone":
            # In zone mode, show zone_type_frame and hide track width controls
            self.track_width_frame.grid_remove()
            self.zone_type_frame.grid()  # ensure zone type controls are visible
        else:  # line mode
            # In line mode, show track width frame and hide zone type controls
            self.zone_type_frame.grid_remove()
            self.track_width_frame.grid()
    
    def select_board_file(self):
        filename = filedialog.askopenfilename(
            title="Select KiCad Board File",
            filetypes=[("KiCad PCB files", "*.kicad_pcb"), ("All files", "*.*")]
        )
        if filename:
            self.board_file_var.set(filename)
            self.board_file = filename
            try:
                self.board = pcbnew.LoadBoard(filename)
                self.update_net_dropdown()  # Populate the dropdown with available nets
                messagebox.showinfo("Success", f"Board loaded: {os.path.basename(filename)}")
            except Exception as e:
                error_msg = f"Failed to load board: {e}\n\nStack trace:\n{traceback.format_exc()}"
                print(error_msg)  # Print to console for full details
                SelectableErrorDialog(self.root, "Error", error_msg)
    
    def update_net_dropdown(self):
        """Update the net dropdown with all nets from the loaded board"""
        if not self.board:
            return
        
        # Extract net names from the board
        self.net_names = []
        nets = self.board.GetNetInfo().NetsByName()
        
        # Add all nets to the dropdown, with GND at the top if it exists
        has_gnd = False
        for name, net in nets.items():
            # Convert from wxString to Python string
            net_name = str(name)
            if net_name.upper() == "GND":
                has_gnd = True
            else:
                self.net_names.append(net_name)
        
        # Sort nets alphabetically
        self.net_names.sort()
        
        # Put GND at the top if it exists
        if has_gnd:
            self.net_names.insert(0, "GND")
        
        # Enable the dropdown now that we have values
        self.net_dropdown.configure(state="readonly")
        
        # Update the dropdown values
        if self.net_names:
            self.net_dropdown['values'] = self.net_names
            self.net_dropdown.set(self.net_names[0])  # Select first net
        else:
            self.net_dropdown['values'] = ["No nets found"]
            self.net_dropdown.set("No nets found")
    
    def select_dxf_file(self):
        filename = filedialog.askopenfilename(
            title="Select DXF File",
            filetypes=[
                ("DXF files", ("*.dxf", "*.DXF")),  # Use tuple for multiple patterns
                ("All files", "*.*")
            ]
        )
        if filename:
            self.dxf_file_var.set(filename)
            self.dxf_file = filename
            # Automatically load the DXF file after selection
            self.load_and_display_dxf()
    
    def load_and_display_dxf(self):
        dxf_file = self.dxf_file_var.get()
        if not dxf_file:
            SelectableMessageDialog(self.root, "Warning", "Please select a DXF file first.", "⚠️")
            return
        
        # Clear existing selections when loading a new DXF file
        self.selected_entities = {}
        self.selected_segments = {}
        
        try:
            if self.heal_gaps.get():
                # Use enhanced loading with gap healing
                self.entities, gap_count = self.load_dxf_with_healing(dxf_file)
                if gap_count > 0:
                    messagebox.showinfo("Gap Healing", f"Healed {gap_count} gaps in the DXF file.")
            else:
                # Use the original loading method
                circles, polylines = load_dxf(dxf_file)
                self.entities = circles + polylines
                
            self.display_dxf_entities()
            # Also refresh the selection list to ensure it's cleared
            self.update_selection_list()
        except Exception as e:
            error_msg = f"Failed to load DXF: {e}\n\nStack trace:\n{traceback.format_exc()}"
            print(error_msg)  # Print to console for full details
            
            # Use the custom dialog instead of messagebox
            SelectableErrorDialog(self.root, "Error", error_msg)

    def load_dxf_with_healing(self, dxf_file):
        """Load DXF file with gap healing functionality"""
        print(f"Reading DXF with gap healing: {dxf_file}")
        try:
            doc = ezdxf.readfile(dxf_file)
            msp = doc.modelspace()
            
            # Extract segments from DXF
            try:
                segments = self.extract_segments_from_dxf(msp)
                self.segments = segments
                
                if not segments:
                    return [], 0
                
                # Only perform gap healing if requested
                if self.heal_gaps.get():
                    try:
                        # Check for gaps first
                        tolerance = self.gap_tolerance.get()
                        print(f"Checking for disconnected segments with tolerance: {tolerance}")
                        endpoints = []
                        for i, (start, end) in enumerate(segments):
                            endpoints.append((start, i, "start"))
                            endpoints.append((end, i, "end"))
                        
                        # Find gaps in the segments
                        gaps = self.find_close_points(endpoints, tolerance)
                        gap_count = len(gaps)
                        print(f"Found {gap_count} potential small gaps between segments")
                        
                        if gap_count > 0:
                            # Only do the healing work if there are actual gaps
                            healed_entities, _ = self.heal_dxf_gaps(segments)
                            return healed_entities, gap_count
                        else:
                            print("No gaps found, converting segments to entities")
                            # Convert segments to proper entities even when no gaps exist
                            entities = self.convert_segments_to_entities(segments, msp)
                            return entities, 0
                            
                    except Exception as e:
                        print(f"ERROR IN GAP HEALING: {e}")
                        print(traceback.format_exc())
                        raise
                else:
                    # Convert segments back to entities even when not healing
                    entities = self.convert_segments_to_entities(segments, msp)
                    return entities, 0
            except Exception as e:
                print(f"ERROR EXTRACTING SEGMENTS: {e}")
                print(traceback.format_exc())
                raise
        except Exception as e:
            print(f"ERROR READING DXF FILE: {e}")
            print(traceback.format_exc())
            raise

    def convert_segments_to_entities(self, segments, msp):
        """Convert extracted segments back to usable entities"""
        # Group connected segments to form polylines
        print(f"Converting {len(segments)} segments to entities")
        
        # Create a new document for clean entities
        doc = ezdxf.new('R2010')
        new_msp = doc.modelspace()
        
        # Collect all original entities by type for reference
        circles = []
        arcs = []
        lines = []
        polylines = []
        
        for e in msp:
            if e.dxftype() == 'CIRCLE':
                circles.append(e)
            elif e.dxftype() == 'ARC':
                arcs.append(e)
            elif e.dxftype() == 'LINE':
                lines.append(e)
            elif e.dxftype() == 'LWPOLYLINE' and e.closed:
                polylines.append(e)
            elif e.dxftype() == 'POLYLINE' and e.is_closed:
                polylines.append(e)

        # Create LineString objects from segments for better processing
        lines_from_segments = [LineString([s[0], s[1]]) for s in segments]
        
        # Try to merge connected lines if possible
        try:
            merged = linemerge(lines_from_segments)
            print(f"Merged into {len(merged.geoms) if hasattr(merged, 'geoms') else 1} linestrings")
            
            # Create entities from merged lines
            entities = []
            
            # First add all circles (exact copies)
            for circle in circles:
                new_circle = new_msp.add_circle(
                    center=circle.dxf.center,
                    radius=circle.dxf.radius
                )
                entities.append(new_circle)
            
            # Then handle merged lines
            if isinstance(merged, LineString):
                # Single merged line
                coords = list(merged.coords)
                if merged.is_closed:
                    # It's a closed loop - make a polyline
                    e = new_msp.add_lwpolyline(coords, close=True)
                    entities.append(e)
                else:
                    # Not closed - add as line segments
                    for i in range(len(coords)-1):
                        e = new_msp.add_line(coords[i], coords[i+1])
                        entities.append(e)
            elif hasattr(merged, 'geoms'):
                # Multiple LineStrings after merging
                for linestring in merged.geoms:
                    coords = list(linestring.coords)
                    if linestring.is_closed:
                        # It's a closed loop - make a polyline
                        e = new_msp.add_lwpolyline(coords, close=True)
                        entities.append(e)
                    else:
                        # Not closed - add as line segments
                        for i in range(len(coords)-1):
                            e = new_msp.add_line(coords[i], coords[i+1])
                            entities.append(e)
            
            # Also try to identify circles from arcs if they form closed loops
            # This is useful for improved visualization and selection
            if arcs:
                # Logic for detecting full circles from arcs would go here
                pass
                
            print(f"Created {len(entities)} entities from segments")
            return entities
        except Exception as e:
            # Fall back to original circles and polylines if merging fails
            print(f"Error merging lines: {e}, using original entities")
            return circles + polylines

    def extract_segments_from_dxf(self, msp):
        segments = []
        try:
            entity_index = 0
            for e in msp:
                print(f"Processing entity #{entity_index} - Type: {e.dxftype()}")
                entity_index += 1
                
                try:
                    if e.dxftype() == 'LINE':
                        print("  Processing LINE")
                        start = e.dxf.start
                        print(f"  LINE start: {start}, type: {type(start)}")
                        if not hasattr(start, '__getitem__'):
                            start = (float(start), 0.0)
                        else:
                            start = (float(start[0]), float(start[1]))
                        end = e.dxf.end
                        print(f"  LINE end: {end}, type: {type(end)}")
                        if not hasattr(end, '__getitem__'):
                            end = (float(end), 0.0)
                        else:
                            end = (float(end[0]), float(end[1]))
                        segments.append((start, end))
                    
                    elif e.dxftype() == 'ARC':
                        print("  Processing ARC")
                        # Extract arc properties
                        center = e.dxf.center
                        radius = e.dxf.radius
                        start_angle = e.dxf.start_angle
                        end_angle = e.dxf.end_angle
                        
                        # Ensure end_angle > start_angle
                        if end_angle < start_angle:
                            end_angle += 360
                            
                        # Number of segments for approximation
                        segments_count = 24  # Good balance of accuracy and performance
                        
                        # Calculate the angle step
                        angle_step = (end_angle - start_angle) / segments_count
                        
                        # Generate arc points
                        arc_pts = []
                        for i in range(segments_count + 1):
                            angle = math.radians(start_angle + i * angle_step)
                            x = center[0] + radius * math.cos(angle)
                            y = center[1] + radius * math.sin(angle)
                            arc_pts.append((x, y))
                        
                        print(f"  Created {len(arc_pts)-1} segments for ARC")
                        segments.extend(zip(arc_pts, arc_pts[1:]))

                    elif e.dxftype() == 'CIRCLE':
                        print("  Processing CIRCLE")
                        center = e.dxf.center
                        radius = e.dxf.radius
                        
                        # Number of segments for approximation (more points for smoother circles)
                        segments_count = 36
                        
                        # Calculate the angle step
                        angle_step = 360 / segments_count
                        
                        # Generate circle points
                        circle_pts = []
                        for i in range(segments_count):
                            angle = math.radians(i * angle_step)
                            x = center[0] + radius * math.cos(angle)
                            y = center[1] + radius * math.sin(angle)
                            circle_pts.append((x, y))
                        
                        # Close the circle
                        circle_pts.append(circle_pts[0])
                        
                        print(f"  Created {len(circle_pts)-1} segments for CIRCLE")
                        segments.extend(zip(circle_pts, circle_pts[1:]))

                    elif e.dxftype() == 'LWPOLYLINE':
                        print("  Processing LWPOLYLINE")
                        points = []
                        try:
                            for pt in e.get_points():
                                coords = (float(pt[0]), float(pt[1]))
                                points.append(coords)
                            if len(points) > 1:
                                if e.closed and points:
                                    points.append(points[0])
                                segments.extend(zip(points, points[1:]))
                        except Exception as lwpoly_err:
                            print(f"  ERROR in LWPOLYLINE processing: {lwpoly_err}")
                            print(traceback.format_exc())
                            continue

                except Exception as entity_err:
                    print(f"ERROR processing entity #{entity_index-1}: {entity_err}")
                    print(traceback.format_exc())
                    continue
            
            print(f"Extracted {len(segments)} segments from DXF")
            return segments
        except Exception as outer_err:
            print(f"ERROR in extract_segments_from_dxf: {outer_err}")
            print(traceback.format_exc())
            raise

    def heal_dxf_gaps(self, segments):
        """Heal gaps in DXF segments using buffer technique with original geometry preservation"""
        if not segments:
            return [], 0
        
        # Gather original entities to preserve them if healing fails
        try:
            doc = ezdxf.readfile(self.dxf_file)
            msp = doc.modelspace()
            original_circles = [e for e in msp if e.dxftype() == 'CIRCLE']
            original_polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and e.closed]
            original_entities = original_circles + original_polylines
            print(f"Preserved {len(original_entities)} original entities in case healing fails")
        except Exception as e:
            print(f"Warning: Could not preserve original entities: {e}")
            original_entities = []
        
        tolerance = self.gap_tolerance.get()
        
        # Check for disconnected segments
        print(f"Checking for disconnected segments with tolerance: {tolerance}")
        endpoints = []
        for i, (start, end) in enumerate(segments):
            endpoints.append((start, i, "start"))
            endpoints.append((end, i, "end"))
        
        # Find gaps in the segments
        gaps = self.find_close_points(endpoints, tolerance)
        gap_count = len(gaps)
        print(f"Found {gap_count} potential small gaps between segments")
        
        if gap_count == 0:
            print("No gaps found, returning original entities")
            return original_entities, 0
        
        # Create LineStrings for shapely processing
        lines = [LineString([s[0], s[1]]) for s in segments]
        
        # Try with buffer to help close small gaps, but use a conservative approach
        print("Attempting to form polygon with conservative buffer technique...")
        
        # Use a more conservative buffer distance
        buffer_distance = min(tolerance, 0.0005)  # Cap at 0.0005 to avoid merging distinct shapes
        print(f"Using buffer distance: {buffer_distance}")
        
        buffered_lines = [line.buffer(buffer_distance) for line in lines]
        buffered_union = unary_union(buffered_lines)
        
        # Convert back to lines and try to create polygons
        simplified = buffered_union.boundary
        
        # Try to create polygons
        healed_entities = []
        
        try:
            # Try to create polygons from the boundary
            polygons = []
            if isinstance(simplified, LineString):
                # Single linestring
                if simplified.is_closed:
                    polygons.extend(list(polygonize([simplified])))
            elif hasattr(simplified, 'geoms'):
                # MultiLineString - try to find closed rings
                rings = []
                for geom in simplified.geoms:
                    if geom.is_closed:
                        rings.append(geom)
                        polygons.extend(list(polygonize([geom])))
                
                # If no polygons were created, try polygonizing all geometries together
                if not polygons and rings:
                    polygons.extend(list(polygonize(rings)))
            
            if polygons:
                # Sort polygons by area (largest first)
                polygons.sort(key=lambda p: p.area, reverse=True)
                
                # Create DXF entities from polygons
                doc = ezdxf.new('R2010')
                msp = doc.modelspace()
                
                for poly in polygons:
                    # Process exterior ring
                    exterior_coords = list(poly.exterior.coords)
                    e = msp.add_lwpolyline(exterior_coords, close=True)
                    healed_entities.append(e)
                    
                    # Process interior rings (holes)
                    if hasattr(poly, 'interiors') and poly.interiors:
                        for interior in poly.interiors:
                            interior_coords = list(interior.coords)
                            e = msp.add_lwpolyline(interior_coords, close=True)
                            healed_entities.append(e)
            else:
                print("Warning: No closed polygons could be formed. Using original entities.")
                return original_entities, 0
                
            # If we have significantly fewer entities than expected, revert to originals
            if len(original_entities) > 0 and len(healed_entities) < len(original_entities) * 0.5:
                print(f"Healing produced too few entities ({len(healed_entities)} vs {len(original_entities)} original). Using originals.")
                return original_entities, 0
                
        except Exception as e:
            print(f"Error during polygon creation: {e}")
            print(traceback.format_exc())
            print("Falling back to original entities.")
            return original_entities, 0
        
        return healed_entities, gap_count

    def find_close_points(self, points, tolerance=0.001):
        """Find points that are close to each other within a tolerance
        
        Args:
            points: List of (point, segment_index, end_type) tuples
            tolerance: Maximum distance between points to be considered 'close'
            
        Returns:
            List of (distance, seg1, end1, seg2, end2, pt1, pt2) tuples for points that are close
        """
        issues = []
        for i, (pt1, seg1, end1) in enumerate(points):
            for j, (pt2, seg2, end2) in enumerate(points[i+1:], i+1):
                if seg1 != seg2:  # Don't compare points from same segment
                    dist = math.sqrt((pt1[0]-pt2[0])**2 + (pt1[1]-pt2[1])**2)
                    if 0 < dist < tolerance:
                        issues.append((dist, seg1, end1, seg2, end2, pt1, pt2))
        return issues

    def on_mouse_wheel(self, event, delta=None):
        """Handle mouse wheel events for zooming centered on cursor position"""
        if delta is None:
            # Windows/macOS uses event.delta
            if hasattr(event, 'delta'):
                delta = event.delta / 120  # Normalize scroll units
            else:
                # Fallback if no delta attribute
                delta = 1 if getattr(event, 'num', 0) == 4 else -1
        
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        
        # Get the mouse position in canvas coordinates
        mouse_x = event.x
        mouse_y = event.y
        
        # Calculate the position in world coordinates before zooming
        world_x = (mouse_x - self.offset_x) / self.scale_factor
        world_y = (canvas_height - mouse_y - self.offset_y) / self.scale_factor
        
        # Determine zoom factor based on direction
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        # Apply zoom by changing scale factor
        old_scale = self.scale_factor
        self.scale_factor *= zoom_factor
        
        # Calculate the new offsets to keep the world point under cursor
        self.offset_x = mouse_x - world_x * self.scale_factor
        self.offset_y = canvas_height - mouse_y - world_y * self.scale_factor
        
        # Redraw with new scale and offset
        self.redraw_entities()

    def start_pan(self, event):
        """Start panning the canvas when the middle mouse button is pressed"""
        self.canvas.scan_mark(event.x, event.y)

    def pan_canvas(self, event):
        """Pan the canvas as the mouse moves with middle button pressed"""
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        
        # Update offset to reflect new pan position
        dx = event.x - self.canvas.canvasx(0)
        dy = event.y - self.canvas.canvasy(0)
        self.offset_x += dx
        self.offset_y += dy

    def on_canvas_press(self, event):
        """Handle mouse button press on canvas"""
        # Find if we clicked directly on an entity
        click_tolerance = 5  # Increased click tolerance
        overlapping_items = self.canvas.find_overlapping(
            event.x-click_tolerance, 
            event.y-click_tolerance, 
            event.x+click_tolerance, 
            event.y+click_tolerance
        )

        if overlapping_items:
            # In zone mode, select any of the overlapping items
            if self.app_mode.get() == "zone":
                # Filter for valid canvas entities
                valid_items = [item for item in overlapping_items if item in self.canvas_entities]
                
                if not valid_items:
                    # No valid items found
                    return
                
                # Sort the items by entity size (smallest first)
                valid_items.sort(key=lambda item: self.get_entity_size(self.canvas_entities[item]))
                    
                # Always select the smallest entity (first in the sorted list)
                selected_entity = valid_items[0]
                    
                # Process the selection
                if selected_entity in self.canvas_entities:
                    self.handle_entity_click(event, selected_entity)
            else:
                # In line mode, just use the first overlapping item as before
                self.handle_entity_click(event, overlapping_items[0])
        else:
            # Start rubber band selection
            self.rubber_band_start = (event.x, event.y)
            self.rubber_band_end = (event.x, event.y)
            self.rubber_band_active = True
            
            # If neither shift nor ctrl key is pressed, clear previous selection
            if not (event.state & 0x0001) and not (event.state & 0x0004):  # Check for shift or ctrl
                if self.app_mode.get() == "line":
                    self.selected_segments = {}
                    self.update_entity_appearance()
                    self.update_selection_list()

    def get_entity_size(self, entity):
        """Calculate approximate size of entity for sorting (smaller values = smaller entity)"""
        if entity.dxftype() == 'CIRCLE':
            # For circles, use area (π × r²)
            return math.pi * entity.dxf.radius ** 2
        elif entity.dxftype() == 'LWPOLYLINE':
            # For polylines, calculate bounding box area
            points = list(entity.get_points())
            if not points:
                return float('inf')  # Empty polyline - treat as very large
                
            min_x = min(pt[0] for pt in points)
            max_x = max(pt[0] for pt in points)
            min_y = min(pt[1] for pt in points)
            max_y = max(pt[1] for pt in points)
            return (max_x - min_x) * (max_y - min_y)
        elif entity.dxftype() == 'LINE':
            # For lines, use length
            start = entity.dxf.start
            end = entity.dxf.end
            return math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2)
        elif entity.dxftype() == 'ARC':
            # For arcs, use arc length
            radius = entity.dxf.radius
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            if end_angle < start_angle:
                end_angle += 360
            angle_rad = math.radians(end_angle - start_angle)
            return radius * angle_rad
        else:
            # Unknown entity type, treat as large
            return float('inf')

    def on_canvas_drag(self, event):
        """Handle mouse drag on canvas"""
        if self.rubber_band_active:
            # Update rubber band end point
            self.rubber_band_end = (event.x, event.y)
            
            # Draw the selection box with style based on drag direction
            self.draw_selection_box()

    def on_canvas_release(self, event):
        """Handle mouse button release on canvas"""
        if self.rubber_band_active:
            # Update final rubber band end point
            self.rubber_band_end = (event.x, event.y)
            
            # Store event state to use in select_*_in_box methods
            self._last_event_state = event.state
            
            # Determine selection mode based on drag direction
            start_x, start_y = self.rubber_band_start
            end_x, end_y = self.rubber_band_end
            
            # If dragging from top-left to bottom-right, use contained mode (strict)
            # Otherwise, use intersect mode (inclusive)
            is_strict_mode = start_x < end_x and start_y < end_y
            
            # Select entities in the rubber band
            if self.app_mode.get() == "line":
                self.select_segments_in_box(is_strict_mode)
            else:  # zone mode
                self.select_entities_in_box(is_strict_mode)
                
            # Clear rubber band selection
            self.clear_selection_box()
            self.rubber_band_active = False

    def draw_selection_box(self):
        """Draw or update the selection box on the canvas"""
        # Delete previous rubber band if it exists
        if self.rubber_band_id:
            self.canvas.delete(self.rubber_band_id)
        
        # Draw new rubber band
        x1, y1 = self.rubber_band_start
        x2, y2 = self.rubber_band_end
        
        # Determine the selection mode based on drag direction
        is_strict_mode = x1 < x2 and y1 < y2
        
        # Use different visual style based on mode:
        # - Solid line for strict/contained mode (top-left to bottom-right)
        # - Dashed line for intersect mode (any other direction)
        dash_pattern = None if is_strict_mode else (4, 4)
        
        self.rubber_band_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="blue", width=1, dash=dash_pattern, 
            fill="blue", stipple="gray12"
        )

    def clear_selection_box(self):
        """Remove the selection box from the canvas"""
        if self.rubber_band_id:
            self.canvas.delete(self.rubber_band_id)
            self.rubber_band_id = None

    def select_segments_in_box(self, strict_mode=False):
        """Select all segments inside or intersecting with the selection box
        
        Args:
            strict_mode: If True, only select segments fully contained within the box
                        If False, select segments that intersect with the box
        """
        if not self.rubber_band_start or not self.rubber_band_end:
            return
        
        # Calculate box coordinates, allowing for selection in any direction
        x1 = min(self.rubber_band_start[0], self.rubber_band_end[0])
        y1 = min(self.rubber_band_start[1], self.rubber_band_end[1])
        x2 = max(self.rubber_band_start[0], self.rubber_band_end[0])
        y2 = max(self.rubber_band_start[1], self.rubber_band_end[1])
        
        # Get items based on selection mode
        if strict_mode:
            # Strict mode - only get items completely enclosed
            items = self.canvas.find_enclosed(x1, y1, x2, y2)
        else:
            # Inclusive mode - get items that overlap with the box
            items = self.canvas.find_overlapping(x1, y1, x2, y2)
        
        # Filter to only select segments in line mode
        selected_count = 0
        
        # Get current state of control key for this drag operation
        control_pressed = self._last_event_state & 0x0004 if hasattr(self, '_last_event_state') else 0
        
        for item in items:
            if item in self.segment_entities:
                segment_key = self.segment_entities[item]
                
                # If control is pressed, remove items from selection
                if control_pressed:
                    if segment_key in self.selected_segments:
                        del self.selected_segments[segment_key]
                        selected_count += 1
                else:
                    # Otherwise add to selection
                    self.selected_segments[segment_key] = True
                    selected_count += 1
        
        # Update the UI to show the selected segments
        if selected_count > 0:
            self.update_entity_appearance()
            self.update_selection_list()

    def select_entities_in_box(self, strict_mode=False):
        """Select all entities inside or intersecting with the selection box
        
        Args:
            strict_mode: If True, only select entities fully contained within the box
                        If False, select entities that intersect with the box
        """
        if not self.rubber_band_start or not self.rubber_band_end:
            return
        
        # Calculate box coordinates, allowing for selection in any direction
        x1 = min(self.rubber_band_start[0], self.rubber_band_end[0])
        y1 = min(self.rubber_band_start[1], self.rubber_band_end[1])
        x2 = max(self.rubber_band_start[0], self.rubber_band_end[0])
        y2 = max(self.rubber_band_start[1], self.rubber_band_end[1])
        
        # Get items based on selection mode
        if strict_mode:
            # Strict mode - only get items completely enclosed
            items = self.canvas.find_enclosed(x1, y1, x2, y2)
        else:
            # Inclusive mode - get items that overlap with the box
            items = self.canvas.find_overlapping(x1, y1, x2, y2)
        
        # Filter to only select entities in zone mode
        boundary_type = self.boundary_type_var.get() == "outer"
        selected_count = 0
        
        # Get current state of control key for this drag operation
        control_pressed = self._last_event_state & 0x0004 if hasattr(self, '_last_event_state') else 0
        
        for item in items:
            if item in self.canvas_entities:
                entity = self.canvas_entities[item]
                
                # If control is pressed, remove items from selection
                if control_pressed:
                    if entity in self.selected_entities:
                        del self.selected_entities[entity]
                        selected_count += 1
                else:
                    # Otherwise add to selection
                    self.selected_entities[entity] = boundary_type
                    selected_count += 1
        
        # Update the UI to show the selected entities
        if selected_count > 0:
            self.update_entity_appearance()
            self.update_selection_list()

    def handle_entity_click(self, event, canvas_id):
        """Handle clicking on an entity"""
        if self.app_mode.get() == "zone":
            # Zone mode - select entire entities
            if canvas_id in self.canvas_entities:
                entity = self.canvas_entities[canvas_id]
                boundary_type = self.boundary_type_var.get() == "outer"
                
                # Check if ctrl key is pressed for removing from selection
                if event.state & 0x0004:  # Ctrl key
                    if entity in self.selected_entities:
                        del self.selected_entities[entity]
                # Check if shift key is pressed for adding to selection
                elif event.state & 0x0001:  # Shift key
                    self.selected_entities[entity] = boundary_type
                else:
                    # No modifier keys: Add to selection or toggle if already selected
                    if entity in self.selected_entities:
                        # If already selected, toggle it off
                        del self.selected_entities[entity]
                    else:
                        # Otherwise, add to selection
                        self.selected_entities[entity] = boundary_type
                
                self.update_entity_appearance()
                self.update_selection_list()
        else:
            # Line mode - select individual segments
            if canvas_id in self.segment_entities:
                segment_key = self.segment_entities[canvas_id]
                
                # Check if ctrl key is pressed for removing from selection
                if event.state & 0x0004:  # Ctrl key
                    if segment_key in self.selected_segments:
                        del self.selected_segments[segment_key]
                # Check if shift key is pressed for adding to selection
                elif event.state & 0x0001:  # Shift key
                    self.selected_segments[segment_key] = True
                else:
                    # No modifier keys: toggle current item, clear all others
                    if segment_key in self.selected_segments and len(self.selected_segments) == 1:
                        # If it's the only selected item, toggle it off
                        self.selected_segments = {}
                    else:
                        # Otherwise, select only this segment
                        self.selected_segments = {segment_key: True}
                
                self.update_entity_appearance()
                self.update_selection_list()

    def on_canvas_motion(self, event):
        """Track mouse position for tooltips"""
        self.mouse_position = (event.x, event.y)

    def _draw_entity(self, entity, canvas_height):
        """Helper method to draw an entity on the canvas with current scale and offset"""
        # In line mode, draw individual segments for selection
        if self.app_mode.get() == "line":
            return self._draw_entity_as_segments(entity, canvas_height)
        
        # In zone mode, draw complete entities
        if entity.dxftype() == 'CIRCLE':
            center = entity.dxf.center
            radius = entity.dxf.radius
            x = center[0] * self.scale_factor + self.offset_x
            y = canvas_height - (center[1] * self.scale_factor + self.offset_y)  # Flip Y
            r = radius * self.scale_factor
            
            canvas_entity = self.canvas.create_oval(
                x - r, y - r, x + r, y + r, 
                outline="black", width=2, fill=""
            )
            self.canvas_entities[canvas_entity] = entity
            return canvas_entity
            
        elif entity.dxftype() == 'LINE':
            start = (entity.dxf.start[0] * self.scale_factor + self.offset_x,
                     canvas_height - (entity.dxf.start[1] * self.scale_factor + self.offset_y))
            end = (entity.dxf.end[0] * self.scale_factor + self.offset_x,
                   canvas_height - (entity.dxf.end[1] * self.scale_factor + self.offset_y))
                   
            canvas_entity = self.canvas.create_line(
                start[0], start[1], end[0], end[1],
                fill="black", width=2
            )
            self.canvas_entities[canvas_entity] = entity
            return canvas_entity
            
        elif entity.dxftype() == 'ARC':
            center = entity.dxf.center
            radius = entity.dxf.radius
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            
            if end_angle < start_angle:
                end_angle += 360
                
            arc_points = []
            segments = 24
            for i in range(segments + 1):
                angle = math.radians(start_angle + (end_angle - start_angle) * i / segments)
                x = center[0] + radius * math.cos(angle)
                y = center[1] + radius * math.sin(angle)
                canvas_x = x * self.scale_factor + self.offset_x
                canvas_y = canvas_height - (y * self.scale_factor + self.offset_y)
                arc_points.append(canvas_x)
                arc_points.append(canvas_y)
                
            if len(arc_points) >= 4:
                canvas_entity = self.canvas.create_line(
                    *arc_points, fill="black", width=2
                )
                self.canvas_entities[canvas_entity] = entity
                return canvas_entity
            return None
            
        elif entity.dxftype() == 'LWPOLYLINE':
            points = entity.get_points()
            canvas_points = []
            for point in points:
                x = point[0] * self.scale_factor + self.offset_x
                y = canvas_height - (point[1] * self.scale_factor + self.offset_y)  # Flip Y
                canvas_points.extend([x, y])
            
            canvas_entity = self.canvas.create_polygon(
                canvas_points, 
                outline="black", 
                fill="", 
                width=2
            )
            self.canvas_entities[canvas_entity] = entity
            return canvas_entity
        
        return None
    
    def _draw_entity_as_segments(self, entity, canvas_height):
        """Draw entity as individual selectable segments for line mode"""
        created_items = []
        
        if entity.dxftype() == 'CIRCLE':
            center = entity.dxf.center
            radius = entity.dxf.radius
            
            # Create segments for circle approximation
            segments_count = 36  # More segments for a smoother circle
            angle_step = 360 / segments_count
            
            # Generate circle points
            circle_pts = []
            for i in range(segments_count):
                angle = math.radians(i * angle_step)
                x = center[0] + radius * math.cos(angle)
                y = center[1] + radius * math.sin(angle)
                circle_pts.append((x, y))
            
            # Close the circle
            circle_pts.append(circle_pts[0])
            
            # Create individual segments
            for i in range(len(circle_pts) - 1):
                start = circle_pts[i]
                end = circle_pts[i + 1]
                
                # Convert to canvas coordinates
                start_x = start[0] * self.scale_factor + self.offset_x
                start_y = canvas_height - (start[1] * self.scale_factor + self.offset_y)
                end_x = end[0] * self.scale_factor + self.offset_x
                end_y = canvas_height - (end[1] * self.scale_factor + self.offset_y)
                
                # Create line
                canvas_id = self.canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill="black", width=2
                )
                self.segment_entities[canvas_id] = (entity, i)
                created_items.append(canvas_id)
        
        elif entity.dxftype() == 'LWPOLYLINE':
            points = list(entity.get_points())
            if entity.closed and points and points[0] != points[-1]:
                points.append(points[0])  # Close the polyline if needed
                
            for i in range(len(points) - 1):
                start = points[i]
                end = points[i + 1]
                
                # Convert to canvas coordinates
                start_x = start[0] * self.scale_factor + self.offset_x
                start_y = canvas_height - (start[1] * self.scale_factor + self.offset_y)
                end_x = end[0] * self.scale_factor + self.offset_x
                end_y = canvas_height - (end[1] * self.scale_factor + self.offset_y)
                
                # Create line
                canvas_id = self.canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill="black", width=2
                )
                self.segment_entities[canvas_id] = (entity, i)
                created_items.append(canvas_id)
                
        elif entity.dxftype() == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            
            # Convert to canvas coordinates
            start_x = start[0] * self.scale_factor + self.offset_x
            start_y = canvas_height - (start[1] * self.scale_factor + self.offset_y)
            end_x = end[0] * self.scale_factor + self.offset_x
            end_y = end[1] * self.scale_factor + self.offset_y
            
            # Create line
            canvas_id = self.canvas.create_line(
                start_x, start_y, end_x, end_y,
                fill="black", width=2
            )
            self.segment_entities[canvas_id] = (entity, 0)
            created_items.append(canvas_id)
            
        elif entity.dxftype() == 'ARC':
            center = entity.dxf.center
            radius = entity.dxf.radius
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            
            if end_angle < start_angle:
                end_angle += 360
                
            # Number of segments for approximation
            segments_count = 24
            angle_step = (end_angle - start_angle) / segments_count
            
            # Generate arc points
            arc_pts = []
            for i in range(segments_count + 1):
                angle = math.radians(start_angle + i * angle_step)
                x = center[0] + radius * math.cos(angle)
                y = center[1] + radius * math.sin(angle)
                arc_pts.append((x, y))
                
            # Create individual segments
            for i in range(len(arc_pts) - 1):
                start = arc_pts[i]
                end = arc_pts[i + 1]
                
                # Convert to canvas coordinates
                start_x = start[0] * self.scale_factor + self.offset_x
                start_y = canvas_height - (start[1] * self.scale_factor + self.offset_y)
                end_x = end[0] * self.scale_factor + self.offset_x
                end_y = canvas_height - (end[1] * self.scale_factor + self.offset_y)
                
                # Create line
                canvas_id = self.canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill="black", width=2
                )
                self.segment_entities[canvas_id] = (entity, i)
                created_items.append(canvas_id)
                
        return created_items

    def display_dxf_entities(self):
        # Clear canvas and reset view
        self.canvas.delete("all")
        self.canvas_entities = {}
        self.segment_entities = {}
        
        # Reset view parameters but don't trigger recursive redraw
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        if not self.entities:
            return
            
        # Find bounding box to calculate scaling
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for entity in self.entities:
            if entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                min_x = min(min_x, center[0] - radius)
                min_y = min(min_y, center[1] - radius)
                max_x = max(max_x, center[0] + radius)
                max_y = max(max_y, center[1] + radius)
            elif entity.dxftype() == 'LWPOLYLINE':
                for point in entity.get_points():
                    min_x = min(min_x, point[0])
                    min_y = min(min_y, point[1])
                    max_x = max(max_x, point[0])
                    max_y = max(max_y, point[1])
        
        # Calculate scale to fit canvas with padding
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        padding = 50
        
        width_scale = (canvas_width - 2 * padding) / (max_x - min_x) if max_x > min_x else 1
        height_scale = (canvas_height - 2 * padding) / (max_y - min_y) if max_y > min_y else 1
        
        self.scale_factor = min(width_scale, height_scale) * 0.9  # 90% of the possible scale
        
        # Calculate offset to center the drawing
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        self.offset_x = canvas_width / 2 - center_x * self.scale_factor
        self.offset_y = canvas_height / 2 - center_y * self.scale_factor
        
        # Flip Y axis because DXF and canvas have different Y-axis directions
        self.offset_y = canvas_height - self.offset_y
        
        # Draw entities using the helper function
        for entity in self.entities:
            self._draw_entity(entity, canvas_height)
        
        # Update selections if any
        self.update_entity_appearance()

    def redraw_entities(self):
        """Redraw entities without resetting view parameters"""
        self.canvas.delete("all")
        self.canvas_entities = {}
        self.segment_entities = {}  # Clear segment mapping as well
        
        if not self.entities:
            return
            
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        
        # Draw entities using the helper function
        for entity in self.entities:
            result = self._draw_entity(entity, canvas_height)
            if isinstance(result, list):  # Multiple canvas items (segments in line mode)
                # Don't store in canvas_entities for line mode
                pass
            elif result:  # Single canvas item (zone mode)
                self.canvas_entities[result] = entity
        
        # Update selections if any
        self.update_entity_appearance()
    
    def update_entity_appearance(self):
        """Reset and update the appearance of all entities"""
        # Use a local flag to avoid recursive calls
        highlighting = getattr(self, '_currently_highlighting', False)
        if highlighting:
            return
        
        if self.app_mode.get() == "zone":
            # Zone mode - highlight entire entities
            for canvas_id, entity in self.canvas_entities.items():
                if entity in self.selected_entities:
                    # Selected - use different colors for outer/inner
                    is_outer = self.selected_entities[entity]
                    color = "blue" if is_outer else "red"
                    if self.canvas.type(canvas_id) == "polygon":
                        self.canvas.itemconfig(canvas_id, outline=color, width=3, fill=color, stipple="gray12")
                    else:  # oval for circle
                        self.canvas.itemconfig(canvas_id, outline=color, width=3, fill=color, stipple="gray12")
                else:
                    # Not selected
                    if self.canvas.type(canvas_id) == "polygon":
                        self.canvas.itemconfig(canvas_id, outline="black", width=2, fill="", stipple="")
                    else:  # oval for circle
                        self.canvas.itemconfig(canvas_id, outline="black", width=2, fill="")
        else:
            # Line mode - highlight individual segments with thicker lines and raise selected items
            for canvas_id, segment_key in self.segment_entities.items():
                if segment_key in self.selected_segments:
                    self.canvas.itemconfig(canvas_id, fill="blue", width=5)  # increased from width=3
                    self.canvas.tag_raise(canvas_id)  # bring selected segment to top
                else:
                    self.canvas.itemconfig(canvas_id, fill="black", width=2)
        
        # After basic appearance is reset, apply any special highlighting needed
        selected_items = self.selection_list.selection()
        if selected_items:
            self._highlight_selected_item_direct(selected_items[0])
    
    def _highlight_selected_item_direct(self, selected_item):
        """Directly highlight the selected item without recursion"""
        try:
            idx = self.selection_list.index(selected_item)
            
            if self.app_mode.get() == "zone":
                # Zone mode
                if idx < len(self.selected_entities):
                    entity = list(self.selected_entities.keys())[idx]
                    for canvas_id, canvas_entity in self.canvas_entities.items():
                        if canvas_entity == entity:
                            # Special highlight for the selected entity
                            is_outer = self.selected_entities[entity]
                            color = "blue" if is_outer else "red"
                            if self.canvas.type(canvas_id) == "polygon":
                                self.canvas.itemconfig(canvas_id, outline=color, width=5, 
                                                    fill=color, stipple="gray12")
                            else:  # oval for circle or line
                                self.canvas.itemconfig(canvas_id, outline=color, width=5, 
                                                    fill=color, stipple="gray12")
                            break
            else:
                # Line mode
                if idx < len(self.selected_segments):
                    segment_key = list(self.selected_segments.keys())[idx]
                    for canvas_id, key in self.segment_entities.items():
                        if key == segment_key:
                            self.canvas.itemconfig(canvas_id, fill="cyan", width=6)  # increased from width=4
                            self.canvas.tag_raise(canvas_id)  # bring highlighted segment to top
                            break
        except Exception as e:
            print(f"Error highlighting tree item: {e}")
    
    def update_selection_list(self):
        # Clear the list
        for item in self.selection_list.get_children():
            self.selection_list.delete(item)
        
        if self.app_mode.get() == "zone":
            # Zone mode - show selected entities
            for entity, is_outer in self.selected_entities.items():
                entity_type = entity.dxftype()
                boundary_type = "Filled zone" if is_outer else "Keepout zone"
                
                # Get a description for the entity
                if entity_type == 'CIRCLE':
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    desc = f"Circle ({center[0]:.2f}, {center[1]:.2f}) r={radius:.2f}"
                elif entity_type == 'LWPOLYLINE':
                    desc = f"Polyline ({len(entity.get_points())} pts)"
                else:
                    desc = entity_type
                    
                item_id = self.selection_list.insert("", tk.END, values=(desc, boundary_type))
                
                # Ensure item is visible
                self.selection_list.see(item_id)
        else:
            # Line mode - show selected segments
            for (entity, segment_idx), _ in self.selected_segments.items():
                entity_type = entity.dxftype()
                
                # Get a description for the segment
                if entity_type == 'CIRCLE':
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    desc = f"Circle segment #{segment_idx+1} (r={radius:.2f})"
                elif entity_type == 'LWPOLYLINE':
                    desc = f"Polyline segment #{segment_idx+1}"
                elif entity_type == 'LINE':
                    desc = f"Line segment"
                elif entity_type == 'ARC':
                    desc = f"Arc segment #{segment_idx+1}"
                else:
                    desc = f"{entity_type} segment #{segment_idx+1}"
                    
                item_id = self.selection_list.insert("", tk.END, values=(desc, "Track"))
                
                # Ensure item is visible
                self.selection_list.see(item_id)
    
    def process_selections(self):
        if not self.board:
            SelectableMessageDialog(self.root, "Warning", "Please load a board file first.", "⚠️")
            return
            
        if self.app_mode.get() == "zone" and not self.selected_entities:
            SelectableMessageDialog(self.root, "Warning", "No entities selected.", "⚠️")
            return
        
        if self.app_mode.get() == "line" and not self.selected_segments:
            SelectableMessageDialog(self.root, "Warning", "No segments selected.", "⚠️")
            return
            
        # Get the selected net name from the dropdown
        net_name = self.net_name_var.get()
        if not net_name or net_name in ["No board loaded", "No nets found"]:
            SelectableMessageDialog(self.root, "Warning", "Please load a board with valid nets first.", "⚠️")
            return
            
        selections = [(entity, is_outer) for entity, is_outer in self.selected_entities.items()]
        
        try:
            # Process based on current mode
            if self.app_mode.get() == "zone":
                process_selections(self.board, selections, net_name)
                message = "Zones created successfully!"
            else:  # line mode
                self.process_line_selections(selections, net_name)
                message = "Tracks created successfully!"
                    
        except Exception as e:
            error_msg = f"Failed to process selections: {e}\n\nStack trace:\n{traceback.format_exc()}"
            print(error_msg)
            SelectableErrorDialog(self.root, "Error", error_msg)
    
    def process_line_selections(self, selections, net_name):
        """Process the selected entities as lines/tracks"""
        # Find the specified net
        net = self.board.FindNet(net_name)
        if not net:
            print(f"Net '{net_name}' not found. Exiting.")
            return
        print(f"Using net '{net_name}' (code {net.GetNetCode()})")
        
        track_width_nm = int(pcbnew.FromMM(self.track_width.get()))
        tracks_added = 0
        
        # Create a single list to collect all tracks for grouping
        all_created_tracks = []
        
        if self.app_mode.get() == "zone":
            # Use the old selection method for zone mode
            
            # Process selected entities
            for entity, _ in selections:  # In line mode we ignore the second parameter
                if entity.dxftype() == 'LINE':
                    track = self.create_track_from_line(entity, net.GetNetCode(), track_width_nm)
                    tracks_added += 1
                    if track:
                        all_created_tracks.append(track)
                elif entity.dxftype() == 'LWPOLYLINE':
                    tracks = self.create_tracks_from_polyline(entity, net.GetNetCode(), track_width_nm)
                    tracks_added += len(tracks)
                    all_created_tracks.extend(tracks)
                elif entity.dxftype() == 'ARC':
                    tracks = self.create_tracks_from_arc(entity, net.GetNetCode(), track_width_nm)
                    tracks_added += len(tracks)
                    all_created_tracks.extend(tracks)
                elif entity.dxftype() == 'CIRCLE':
                    tracks = self.create_tracks_from_circle(entity, net.GetNetCode(), track_width_nm)
                    tracks_added += len(tracks)
                    all_created_tracks.extend(tracks)
        else:
            # New selection method for line mode - track-by-track
            
            # Process selected segments individually
            for (entity, segment_idx), _ in self.selected_segments.items():
                if entity.dxftype() == 'CIRCLE':
                    track = self.create_track_from_circle_segment(entity, segment_idx, net.GetNetCode(), track_width_nm)
                    tracks_added += 1
                    if track:
                        all_created_tracks.append(track)
                elif entity.dxftype() == 'LWPOLYLINE':
                    track = self.create_track_from_polyline_segment(entity, segment_idx, net.GetNetCode(), track_width_nm)
                    tracks_added += 1
                    if track:
                        all_created_tracks.append(track)
                elif entity.dxftype() == 'LINE':
                    track = self.create_track_from_line(entity, net.GetNetCode(), track_width_nm)
                    tracks_added += 1
                    if track:
                        all_created_tracks.append(track)
                elif entity.dxftype() == 'ARC':
                    track = self.create_track_from_arc_segment(entity, segment_idx, net.GetNetCode(), track_width_nm)
                    tracks_added += 1
                    if track:
                        all_created_tracks.append(track)
        
        # Create a single group for all created tracks
        if all_created_tracks:
            # Extract the DXF filename without path and extension
            dxf_filename = os.path.basename(self.dxf_file)
            dxf_basename = os.path.splitext(dxf_filename)[0]  # Remove extension
            
            # Use DXF filename in group name
            group_name = f"{dxf_basename} - {net_name}"
            self.group_tracks(all_created_tracks, group_name)
        
        print(f"Added {tracks_added} tracks to the board.")

    def get_entity_description(self, entity):
        """Get a human-readable description of an entity for group naming"""
        entity_type = entity.dxftype()
        
        if entity_type == 'CIRCLE':
            center = entity.dxf.center
            radius = entity.dxf.radius
            return f"Circle r={radius:.2f}"
        elif entity_type == 'LWPOLYLINE':
            return f"Polyline ({len(entity.get_points())} pts)"
        elif entity_type == 'LINE':
            return f"Line"
        elif entity_type == 'ARC':
            return f"Arc"
        else:
            return entity_type

    def group_tracks(self, tracks, group_name):
        """Group the provided tracks together with the given name"""
        if not tracks or len(tracks) < 2:
            return  # No need to group a single track
        
        try:
            # Create a group (available in KiCad 6.0+)
            if hasattr(pcbnew, 'PCB_GROUP'):
                group = pcbnew.PCB_GROUP(self.board)
                group.SetName(group_name)
                
                # Add all tracks to the group
                for track in tracks:
                    group.AddItem(track)
                    
                # Add the group to the board
                self.board.Add(group)
                print(f"Created group '{group_name}' with {len(tracks)} tracks")
            else:
                print(f"Note: KiCad version does not support grouping")
        except Exception as e:
            # If grouping fails (e.g., on older KiCad versions), just log a message
            print(f"Note: Could not create group '{group_name}': {e}")

    def create_track_from_line(self, entity, net_code, track_width):
        """Create a KiCad track from a DXF LINE entity"""
        start = entity.dxf.start
        end = entity.dxf.end
        
        # Updated for KiCad 9: Use PCB_TRACK with VECTOR2I instead of wxPoint
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                       int(pcbnew.FromMM(float(start[1])))))
        track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                     int(pcbnew.FromMM(float(end[1])))))
        track.SetLayer(pcbnew.F_Cu)  # Default to front copper
        track.SetNetCode(net_code)
        track.SetWidth(track_width)
        
        self.board.Add(track)
        print(f"Added track from ({start[0]:.2f}, {start[1]:.2f}) to ({end[0]:.2f}, {end[1]:.2f})")
        return track  # Return the created track object

    def create_tracks_from_polyline(self, entity, net_code, track_width):
        """Create KiCad tracks from a DXF LWPOLYLINE entity"""
        points = list(entity.get_points())
        if len(points) < 2:
            return []
        
        created_tracks = []  # Keep track of created tracks
        
        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1]
            
            # Updated for KiCad 9: Use PCB_TRACK with VECTOR2I instead of wxPoint
            track = pcbnew.PCB_TRACK(self.board)
            track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                           int(pcbnew.FromMM(float(start[1])))))
            track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                         int(pcbnew.FromMM(float(end[1])))))
            track.SetLayer(pcbnew.F_Cu)  # Default to front copper
            track.SetNetCode(net_code)
            track.SetWidth(track_width)
            
            self.board.Add(track)
            created_tracks.append(track)
        
        # Close the loop if the polyline is closed
        if entity.closed and len(points) > 1 and (points[0] != points[-1]):
            start = points[-1]
            end = points[0]
            
            # Updated for KiCad 9: Use PCB_TRACK with VECTOR2I instead of wxPoint
            track = pcbnew.PCB_TRACK(self.board)
            track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                           int(pcbnew.FromMM(float(start[1])))))
            track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                         int(pcbnew.FromMM(float(end[1])))))
            track.SetLayer(pcbnew.F_Cu)  # Default to front copper
            track.SetNetCode(net_code)
            track.SetWidth(track_width)
            
            self.board.Add(track)
            created_tracks.append(track)
        
        print(f"Added {len(created_tracks)} tracks from polyline")
        return created_tracks  # Return the list of created tracks

    def create_tracks_from_arc(self, entity, net_code, track_width):
        """Create KiCad tracks from a DXF ARC entity"""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle
        
        # Ensure end_angle > start_angle
        if end_angle < start_angle:
            end_angle += 360
            
        # Number of segments for approximation
        segments_count = 24  # Good balance of accuracy and performance
        
        # Calculate the angle step
        angle_step = (end_angle - start_angle) / segments_count
        
        # Generate arc points
        arc_pts = []
        for i in range(segments_count + 1):
            angle = math.radians(start_angle + i * angle_step)
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            arc_pts.append((x, y))
        
        # Create tracks between the points
        created_tracks = []
        for i in range(len(arc_pts) - 1):
            start = arc_pts[i]
            end = arc_pts[i + 1]
            
            # Updated for KiCad 9: Use PCB_TRACK with VECTOR2I instead of wxPoint
            track = pcbnew.PCB_TRACK(self.board)
            track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                           int(pcbnew.FromMM(float(start[1])))))
            track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                         int(pcbnew.FromMM(float(end[1])))))
            track.SetLayer(pcbnew.F_Cu)  # Default to front copper
            track.SetNetCode(net_code)
            track.SetWidth(track_width)
            
            self.board.Add(track)
            created_tracks.append(track)
        
        print(f"Added {len(created_tracks)} tracks for arc")
        return created_tracks  # Return the list of created tracks

    def create_tracks_from_circle(self, entity, net_code, track_width):
        """Create KiCad tracks from a DXF CIRCLE entity"""
        center = entity.dxf.center
        radius = entity.dxf.radius
        
        # Number of segments for approximation
        segments_count = 36  # More segments for a smoother circle
        
        # Calculate the angle step
        angle_step = 360 / segments_count
        
        # Generate circle points
        circle_pts = []
        for i in range(segments_count):
            angle = math.radians(i * angle_step)
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            circle_pts.append((x, y))
        
        # Close the circle
        circle_pts.append(circle_pts[0])
        
        # Create tracks between the points
        created_tracks = []
        for i in range(len(circle_pts) - 1):
            start = circle_pts[i]
            end = circle_pts[i + 1]
            
            # Updated for KiCad 9: Use PCB_TRACK with VECTOR2I instead of wxPoint
            track = pcbnew.PCB_TRACK(self.board)
            track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                           int(pcbnew.FromMM(float(start[1])))))
            track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                         int(pcbnew.FromMM(float(end[1])))))
            track.SetLayer(pcbnew.F_Cu)  # Default to front copper
            track.SetNetCode(net_code)
            track.SetWidth(track_width)
            
            self.board.Add(track)
            created_tracks.append(track)
        
        print(f"Added {len(created_tracks)} tracks for circle")
        return created_tracks  # Return the list of created tracks

    def create_track_from_circle_segment(self, entity, segment_idx, net_code, track_width):
        """Create a single track from a circle segment"""
        center = entity.dxf.center
        radius = entity.dxf.radius
        
        # Number of segments for approximation
        segments_count = 36  # Same as in drawing
        angle_step = 360 / segments_count
        
        # Calculate start and end angles for this segment
        start_angle = segment_idx * angle_step
        end_angle = (segment_idx + 1) * angle_step
        
        # Calculate points
        start_angle_rad = math.radians(start_angle)
        end_angle_rad = math.radians(end_angle)
        
        start = (center[0] + radius * math.cos(start_angle_rad), 
                 center[1] + radius * math.sin(start_angle_rad))
        end = (center[0] + radius * math.cos(end_angle_rad), 
               center[1] + radius * math.sin(end_angle_rad))
        
        # Create track
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                       int(pcbnew.FromMM(float(start[1])))))
        track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                     int(pcbnew.FromMM(float(end[1])))))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNetCode(net_code)
        track.SetWidth(track_width)
        
        self.board.Add(track)
        return track  # Return the created track

    def create_track_from_polyline_segment(self, entity, segment_idx, net_code, track_width):
        """Create a single track from a polyline segment"""
        points = list(entity.get_points())
        if segment_idx >= len(points) - 1:
            if entity.closed and points:
                # It's a closing segment between last and first point
                start = points[-1]
                end = points[0]
            else:
                # Invalid segment index
                return None
        else:
            # Normal segment
            start = points[segment_idx]
            end = points[segment_idx + 1]
        
        # Create track
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start[0]))),
                                       int(pcbnew.FromMM(float(start[1])))))
        track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end[0]))),
                                     int(pcbnew.FromMM(float(end[1])))))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNetCode(net_code)
        track.SetWidth(track_width)
        
        self.board.Add(track)
        return track  # Return the created track

    def create_track_from_arc_segment(self, entity, segment_idx, net_code, track_width):
        """Create a single track from an arc segment"""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle
        
        if end_angle < start_angle:
            end_angle += 360
            
        # Number of segments for approximation
        segments_count = 24  # Same as in drawing
        angle_step = (end_angle - start_angle) / segments_count
        
        # Calculate points for the specific segment
        segment_start_angle = start_angle + segment_idx * angle_step
        segment_end_angle = start_angle + (segment_idx + 1) * angle_step
        
        start_x = center[0] + radius * math.cos(math.radians(segment_start_angle))
        start_y = center[1] + radius * math.sin(math.radians(segment_start_angle))
        end_x = center[0] + radius * math.cos(math.radians(segment_end_angle))
        end_y = center[1] + radius * math.sin(math.radians(segment_end_angle))
        
        # Create track
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(start_x))),
                                       int(pcbnew.FromMM(float(start_y)))))
        track.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(float(end_x))),
                                     int(pcbnew.FromMM(float(end_y)))))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNetCode(net_code)
        track.SetWidth(track_width)
        
        self.board.Add(track)
        return track  # Return the created track

    def save_board(self):
        """Save changes back to the original board file"""
        if not self.board:
            SelectableMessageDialog(self.root, "Warning", "No board loaded.", "⚠️")
            return
            
        if not self.board_file:
            # If no file was specified yet, use Save As
            self.save_board_as()
            return
            
        try:
            pcbnew.SaveBoard(self.board_file, self.board)
            messagebox.showinfo("Success", f"Board saved to: {self.board_file}")
        except Exception as e:
            error_msg = f"Failed to save board: {e}\n\nStack trace:\n{traceback.format_exc()}"
            print(error_msg)
            SelectableErrorDialog(self.root, "Error", error_msg)
    
    def save_board_as(self):
        if not self.board:
            SelectableMessageDialog(self.root, "Warning", "No board loaded.", "⚠️")
            return
            
        filename = filedialog.asksaveasfilename(
            title="Save KiCad Board",
            filetypes=[("KiCad PCB files", "*.kicad_pcb"), ("All files", "*.*")],
            defaultextension=".kicad_pcb"
        )
        
        if filename:
            try:
                pcbnew.SaveBoard(filename, self.board)
                # Update the current board file to the new one
                self.board_file = filename
                self.board_file_var.set(filename)
                messagebox.showinfo("Success", f"Board saved to: {filename}")
            except Exception as e:
                error_msg = f"Failed to save board: {e}\n\nStack trace:\n{traceback.format_exc()}"
                print(error_msg)
                SelectableErrorDialog(self.root, "Error", error_msg)

    def process_and_save(self):
        """Process selections then save the board."""
        self.process_selections()
        self.save_board()

    def process_and_save_as(self):
        """Process selections then perform Save As."""
        self.process_selections()
        self.save_board_as()

    def exit_application(self, event=None):
        """Close the application when Escape is pressed or Exit button clicked"""
        self.root.destroy()

    def change_entity_type(self):
        """Toggle the type of the selected entity between filled zone and keepout zone"""
        # Get the selected item from the treeview
        selected_items = self.selection_list.selection()
        if not selected_items:
            return  # No item selected
            
        # Get the index of the selected item
        idx = self.selection_list.index(selected_items[0])
        
        # Make sure we're in zone mode and have entities selected
        if self.app_mode.get() != "zone" or not self.selected_entities:
            return
            
        # Get the entity at the selected index
        entity = list(self.selected_entities.keys())[idx]
        
        # Toggle its type (True for outer/filled, False for inner/keepout)
        self.selected_entities[entity] = not self.selected_entities[entity]
        
        # Update the UI
        self.update_entity_appearance()
        self.update_selection_list()
    
    def remove_selection(self, event=None):
        """Remove the selected entity from the selection list"""
        # Get the selected item from the treeview
        selected_items = self.selection_list.selection()
        if not selected_items:
            return  # No item selected
            
        # Get the index of the selected item
        idx = self.selection_list.index(selected_items[0])
        
        if self.app_mode.get() == "zone":
            # In zone mode, remove the entity
            if idx < len(self.selected_entities):
                entity = list(self.selected_entities.keys())[idx]
                del self.selected_entities[entity]
        else:
            # In line mode, remove the segment
            if idx < len(self.selected_segments):
                segment_key = list(self.selected_segments.keys())[idx]
                del self.selected_segments[segment_key]
        
        # Update the UI
        self.update_entity_appearance()
        self.update_selection_list()
    
    def show_context_menu(self, event):
        """Show context menu for the selection list on right click"""
        # Get the item under the cursor
        item = self.selection_list.identify_row(event.y)
        if item:
            # Select the item under the cursor
            self.selection_list.selection_set(item)
            # Show the context menu
            self.context_menu.post(event.x_root, event.y_root)
    
    def highlight_selected_entity(self, event):
        """Highlight the selected entity in the drawing when selected in the list"""
        # Don't need to implement the highlight logic here since _highlight_selected_item_direct
        # is already called from update_entity_appearance
        self.update_entity_appearance()

    def reset_view(self):
        """Reset the view to fit all entities"""
        if not self.entities:
            return
            
        # Simply redisplay all entities with default view parameters
        self.display_dxf_entities()

# Keep these functions as they are for compatibility
def load_dxf(dxf_file):
    """Load DXF file and return its entities"""
    print(f"Reading DXF: {dxf_file}")
    doc = ezdxf.readfile(dxf_file)
    msp = doc.modelspace()
    
    # Get entities by type
    circles = [e for e in msp if e.dxftype() == 'CIRCLE']
    polylines = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and e.closed]
    
    print(f"Found {len(circles)} circles and {len(polylines)} closed polylines.")
    return circles, polylines

def describe_entity(entity, index):
    """Generate a description for an entity"""
    if entity.dxftype() == 'CIRCLE':
        center = entity.dxf.center
        radius = entity.dxf.radius
        return f"{index}. Circle at ({center[0]:.2f}, {center[1]:.2f}) with radius {radius:.2f}"
    elif entity.dxftype() == 'LWPOLYLINE':
        points = list(entity.get_points())
        return f"{index}. Polyline with {len(points)} points"
    return f"{index}. Unknown entity type: {entity.dxftype()}"

def create_zone_for_entity(board, entity, net_code):
    """Create a zone for the given entity"""
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.F_Cu)
    zone.SetNetCode(net_code)
    
    outline = zone.Outline()
    outline.NewOutline()
    
    if entity.dxftype() == 'CIRCLE':
        # Approximate circle with points
        center = entity.dxf.center
        radius = entity.dxf.radius
        num_points = 36
        
        for i in range(num_points + 1):  # +1 to close the loop
            angle = 2 * math.pi * i / num_points
            x = float(center[0] + radius * math.cos(angle))
            y = float(center[1] + radius * math.sin(angle))
            point = pcbnew.wxPointMM(x, y)
            outline.Append(point.x, point.y)
    
    elif entity.dxftype() == 'LWPOLYLINE':
        # Add polyline points
        for pt in entity.get_points():
            point = pcbnew.wxPointMM(float(pt[0]), float(pt[1]))
            outline.Append(point.x, point.y)
    
    return zone

def add_cutout_to_zone(zone, entity):
    """Add an entity as a cutout to the zone"""
    # The most reliable approach is to use a keepout zone
    # This avoids potential segfaults with the AddOutline method
    board = zone.GetBoard()
    
    # Create points for the cutout
    if entity.dxftype() == 'CIRCLE':
        center = entity.dxf.center
        radius = entity.dxf.radius
        num_points = 36
        points = []
        
        # Create points for circle (counter-clockwise)
        for i in range(num_points):
            angle = 2 * math.pi * (num_points - i - 1) / num_points  # Counter-clockwise
            x = float(center[0] + radius * math.cos(angle))
            y = float(center[1] + radius * math.sin(angle))
            points.append(pcbnew.wxPointMM(x, y))
        
        # Close the outline
        points.append(points[0])
    elif entity.dxftype() == 'LWPOLYLINE':
        points = []
        for pt in entity.get_points():
            points.append(pcbnew.wxPointMM(float(pt[0]), float(pt[1])))
        # Close the outline if needed
        if points[0].x != points[-1].x or points[0].y != points[-1].y:
            points.append(points[0])
    
    # Create a reliable keepout zone (always works without crashing)
    keepout = pcbnew.ZONE(board)
    keepout.SetLayer(zone.GetLayer())
    keepout.SetIsRuleArea(True)
    keepout.SetDoNotAllowCopperPour(True)
    
    # Create the keepout outline
    k_outline = keepout.Outline()
    k_outline.NewOutline()
    for p in points:
        k_outline.Append(p.x, p.y)
    
    board.Add(keepout)
    print("  Added keepout zone as hole")

def process_selections(board, selections, net_name):
    """Process the selected entities"""
    if not selections:
        print("No entities selected. Exiting.")
        return
    
    # Find the specified net
    net = board.FindNet(net_name)
    if not net:
        print(f"Net '{net_name}' not found. Exiting.")
        return
    print(f"Using net '{net_name}' (code {net.GetNetCode()})")
    
    # Group selections by outer and inner
    outer_entities = [e for e, is_outer in selections if is_outer]
    inner_entities = [e for e, is_outer in selections if not is_outer]
    
    # Process outer entities first
    for idx, entity in enumerate(outer_entities):
        print(f"Processing outer entity {idx+1}...")
        zone = create_zone_for_entity(board, entity, net.GetNetCode())
        
        # Find any inner entities that should be cutouts for this outer entity
        # For simplicity, we'll just use them all as cutouts for now
        for inner_idx, inner_entity in enumerate(inner_entities):
            try:
                add_cutout_to_zone(zone, inner_entity)
                print(f"  Added inner entity {inner_idx+1} as cutout")
            except Exception as e:
                print(f"  Failed to add inner entity {inner_idx+1} as cutout: {e}")
        
        board.Add(zone)
        print(f"Zone added for outer entity {idx+1}")
    
    # Fill all zones
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print("All zones filled.")

def main():
    root = tk.Tk()
    app = KicadDxfApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
