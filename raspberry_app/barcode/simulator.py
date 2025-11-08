"""
Barcode scanner simulator for development and testing.
Provides GUI for manual barcode entry without physical hardware.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, List
import time

from raspberry_app.barcode.validator import BarcodeValidator
from raspberry_app.utils.logger import LoggerMixin


class BarcodeSimulator(LoggerMixin):
    """
    GUI barcode simulator for development without hardware.

    Provides:
    - Manual barcode entry field
    - Product selection dropdown
    - Quick-scan buttons for common products
    - Validation feedback
    - Scan history

    Example:
        >>> simulator = BarcodeSimulator(callback=lambda b: print(f"Scanned: {b}"))
        >>> simulator.start()
    """

    def __init__(self, callback: Optional[Callable[[str], None]] = None,
                 validator: Optional[BarcodeValidator] = None,
                 sample_products: Optional[List[dict]] = None):
        """
        Initialize barcode simulator.

        Args:
            callback: Function to call when barcode is "scanned"
            validator: BarcodeValidator instance
            sample_products: List of sample products with 'ean' and 'name'
        """
        self.callback = callback
        self.validator = validator or BarcodeValidator()
        self.sample_products = sample_products or []

        self.root: Optional[tk.Tk] = None
        self.barcode_entry: Optional[tk.Entry] = None
        self.product_combo: Optional[ttk.Combobox] = None
        self.history_listbox: Optional[tk.Listbox] = None
        self.status_label: Optional[tk.Label] = None  # Using tk.Label for fg support

        self.scan_history: List[str] = []
        self.running = False

    def set_callback(self, callback: Callable[[str], None]):
        """Set callback function for scanned barcodes."""
        self.callback = callback

    def load_sample_products(self, products: List[dict]):
        """
        Load sample products for quick selection.

        Args:
            products: List of dicts with 'ean' and 'name' keys
        """
        self.sample_products = products
        if self.product_combo:
            self._update_product_list()

    def _update_product_list(self):
        """Update product combobox with sample products."""
        if not self.product_combo:
            return

        product_list = [f"{p['ean']} - {p['name']}" for p in self.sample_products]
        self.product_combo['values'] = product_list

    def _process_barcode(self, barcode: str):
        """
        Process and validate barcode.

        Args:
            barcode: Barcode string to process
        """
        # Clean input
        barcode = barcode.strip()

        if not barcode:
            self._update_status("❌ Empty barcode", "error")
            return

        # Validate
        if not self.validator.validate(barcode):
            self._update_status(f"❌ Invalid barcode: {barcode}", "error")
            messagebox.showerror("Invalid Barcode",
                               f"Barcode '{barcode}' is not a valid EAN-13 code")
            return

        # Format
        formatted = self.validator.format(barcode)
        if not formatted:
            self._update_status(f"❌ Could not format: {barcode}", "error")
            return

        # Add to history
        self.scan_history.append(formatted)
        if self.history_listbox:
            self.history_listbox.insert(0, f"{time.strftime('%H:%M:%S')} - {formatted}")
            # Limit history to 50 items
            if self.history_listbox.size() > 50:
                self.history_listbox.delete(50, tk.END)

        # Update status
        self._update_status(f"✅ Scanned: {formatted}", "success")

        # Call callback
        if self.callback:
            try:
                self.callback(formatted)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}")
                self._update_status(f"❌ Callback error: {e}", "error")

        # Clear entry
        if self.barcode_entry:
            self.barcode_entry.delete(0, tk.END)

    def _update_status(self, message: str, status_type: str = "info"):
        """Update status label."""
        if not self.status_label:
            return

        colors = {
            "success": "#28a745",
            "error": "#dc3545",
            "info": "#17a2b8"
        }

        self.status_label.config(text=message, fg=colors.get(status_type, "#000000"))

    def _on_scan_button(self):
        """Handle scan button click."""
        if self.barcode_entry:
            barcode = self.barcode_entry.get()
            self._process_barcode(barcode)

    def _on_entry_return(self, event):
        """Handle Enter key in entry field."""
        self._on_scan_button()

    def _on_product_select(self, event):
        """Handle product selection from dropdown."""
        if not self.product_combo:
            return

        selection = self.product_combo.get()
        if selection:
            # Extract EAN from selection (format: "EAN - Name")
            ean = selection.split(" - ")[0]
            if self.barcode_entry:
                self.barcode_entry.delete(0, tk.END)
                self.barcode_entry.insert(0, ean)
            # Auto-scan
            self._process_barcode(ean)

    def _on_clear_history(self):
        """Clear scan history."""
        if self.history_listbox:
            self.history_listbox.delete(0, tk.END)
        self.scan_history.clear()
        self._update_status("History cleared", "info")

    def _create_ui(self):
        """Create simulator UI."""
        self.root = tk.Tk()
        self.root.title("Barcode Scanner Simulator")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(main_frame, text="📱 Barcode Scanner Simulator",
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Manual Entry Section
        entry_frame = ttk.LabelFrame(main_frame, text="Manual Entry", padding="10")
        entry_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(entry_frame, text="EAN-13:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        self.barcode_entry = ttk.Entry(entry_frame, width=30, font=("Courier", 12))
        self.barcode_entry.grid(row=0, column=1, padx=(0, 10))
        self.barcode_entry.bind('<Return>', self._on_entry_return)
        self.barcode_entry.focus()

        scan_button = ttk.Button(entry_frame, text="Scan", command=self._on_scan_button)
        scan_button.grid(row=0, column=2)

        # Product Selection Section
        product_frame = ttk.LabelFrame(main_frame, text="Quick Select Product", padding="10")
        product_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(product_frame, text="Product:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        self.product_combo = ttk.Combobox(product_frame, width=50, state="readonly")
        self.product_combo.grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.product_combo.bind('<<ComboboxSelected>>', self._on_product_select)

        self._update_product_list()

        # Scan History Section
        history_frame = ttk.LabelFrame(main_frame, text="Scan History", padding="10")
        history_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Scrollbar
        scrollbar = ttk.Scrollbar(history_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.history_listbox = tk.Listbox(history_frame, height=10,
                                          yscrollcommand=scrollbar.set,
                                          font=("Courier", 10))
        self.history_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.history_listbox.yview)

        # Clear history button
        clear_button = ttk.Button(history_frame, text="Clear History",
                                 command=self._on_clear_history)
        clear_button.grid(row=1, column=0, columnspan=2, pady=(5, 0))

        # Status Bar
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        self.status_label = tk.Label(status_frame, text="Ready to scan...",
                                     font=("Arial", 10), fg="#17a2b8")
        self.status_label.grid(row=0, column=0, sticky=tk.W)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        history_frame.columnconfigure(0, weight=1)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        self.logger.info("Barcode simulator UI created")

    def start(self, callback: Optional[Callable[[str], None]] = None):
        """
        Start the simulator GUI.

        Args:
            callback: Optional callback for scanned barcodes
        """
        if callback:
            self.set_callback(callback)

        self.running = True
        self._create_ui()

        self.logger.info("Starting barcode simulator")
        self.root.mainloop()

    def stop(self):
        """Stop the simulator."""
        self.running = False
        if self.root:
            self.root.quit()
            self.root.destroy()
        self.logger.info("Barcode simulator stopped")


# Example usage
if __name__ == "__main__":
    def on_barcode_scanned(barcode: str):
        """Callback for scanned barcodes."""
        print(f"📦 Product scanned: {barcode}")

    # Sample products for testing
    sample_products = [
        {"ean": "8470001234567", "name": "Ibuprofeno 600mg"},
        {"ean": "8470002345678", "name": "Omeprazol 20mg"},
        {"ean": "8470003456789", "name": "Paracetamol 1g"},
        {"ean": "8470004567890", "name": "Aspirina 500mg"},
        {"ean": "8470005678901", "name": "Nolotil 575mg"},
    ]

    print("=" * 60)
    print("BARCODE SIMULATOR")
    print("=" * 60)
    print("\nStarting simulator GUI...")
    print("Use the GUI to scan barcodes")
    print()

    simulator = BarcodeSimulator(
        callback=on_barcode_scanned,
        sample_products=sample_products
    )

    try:
        simulator.start()
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping...")
        simulator.stop()
        print("✅ Stopped")
