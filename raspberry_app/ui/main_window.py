"""
Main application window for the pharmacy recommendation system.
Integrates cart, recommendations, barcode scanning, and API calls.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import logging
from typing import List, Dict, Optional
from collections import defaultdict

from raspberry_app.config import config
from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.database.models import Product
from raspberry_app.api.cache_manager import CacheManager
from raspberry_app.api.claude_client import ClaudeClient
from raspberry_app.barcode.simulator import BarcodeSimulator
from raspberry_app.ui.styles import COLORS, get_priority_color, get_priority_frame_style
from raspberry_app.utils.logger import LoggerMixin


class MainWindow(LoggerMixin):
    """
    Main application window.

    Manages:
    - Shopping cart display
    - Product scanning
    - Recommendation display
    - Database and API integration
    - Threading for non-blocking UI
    """

    def __init__(self, root: tk.Tk):
        """
        Initialize main window.

        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("Sistema de Recomendación Farmacéutica")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.resizable(True, True)
        self.root.minsize(800, 600)

        # Components
        self.db = DatabaseManager()
        self.cache_manager = CacheManager(
            max_size=config.CACHE_MAX_SIZE,
            ttl=config.CACHE_TTL
        )

        # Initialize Claude client if API key is configured
        try:
            self.claude_client = ClaudeClient(self.cache_manager)
            self.api_available = True
        except ValueError as e:
            self.logger.warning(f"Claude API not available: {e}")
            self.api_available = False

        # State
        self.cart: List[Dict] = []  # List of product dicts
        self.cart_counts = defaultdict(int)  # product_id -> quantity
        self.current_recommendations: List[Dict] = []
        self.debounce_timer: Optional[str] = None
        self.simulator: Optional[BarcodeSimulator] = None

        # UI elements
        self.cart_tree: Optional[ttk.Treeview] = None
        self.total_label: Optional[ttk.Label] = None
        self.recommendations_canvas: Optional[tk.Canvas] = None
        self.rec_inner_frame: Optional[ttk.Frame] = None
        self.status_label: Optional[ttk.Label] = None

        self.create_widgets()

        # Note: Simulator can be opened manually via button
        # Auto-open can cause issues with multiple Tk windows in Docker
        # if config.SIMULATION_MODE:
        #     self.open_simulator()

        self.logger.info("Main window initialized")

    def create_widgets(self):
        """Create all UI widgets."""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Two-panel layout
        left_panel = ttk.Frame(main_container)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 5))

        right_panel = ttk.Frame(main_container)
        right_panel.pack(side='right', fill='both', expand=True, padx=(5, 0))

        # Create panels
        self.create_cart_panel(left_panel)
        self.create_recommendations_panel(right_panel)

        # Toolbar at bottom
        self.create_toolbar(main_container)

        self.logger.info("Widgets created")

    def create_cart_panel(self, parent):
        """Create cart panel (left side)."""
        # Title
        title = ttk.Label(parent, text="Carrito de Compra", style='Subtitle.TLabel')
        title.pack(pady=(0, 10))

        # Treeview for cart items
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side='right', fill='y')

        # Treeview
        self.cart_tree = ttk.Treeview(
            tree_frame,
            columns=('quantity', 'name', 'price', 'subtotal'),
            show='headings',
            style='Cart.Treeview',
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.cart_tree.yview)

        # Configure columns
        self.cart_tree.heading('quantity', text='Cant.')
        self.cart_tree.heading('name', text='Producto')
        self.cart_tree.heading('price', text='Precio')
        self.cart_tree.heading('subtotal', text='Subtotal')

        self.cart_tree.column('quantity', width=60, anchor='center')
        self.cart_tree.column('name', width=250)
        self.cart_tree.column('price', width=80, anchor='e')
        self.cart_tree.column('subtotal', width=80, anchor='e')

        self.cart_tree.pack(side='left', fill='both', expand=True)

        # Total
        total_frame = ttk.Frame(parent)
        total_frame.pack(fill='x', pady=10)

        ttk.Label(total_frame, text="TOTAL:", style='Total.TLabel').pack(side='left')
        self.total_label = ttk.Label(total_frame, text="€0.00", style='Total.TLabel')
        self.total_label.pack(side='right')

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', pady=5)

        ttk.Button(
            button_frame,
            text="Eliminar",
            style='Danger.TButton',
            command=self.remove_item
        ).pack(side='left', padx=2, fill='x', expand=True)

        ttk.Button(
            button_frame,
            text="Nueva Compra",
            style='Primary.TButton',
            command=self.new_sale
        ).pack(side='left', padx=2, fill='x', expand=True)

        ttk.Button(
            button_frame,
            text="Finalizar",
            style='Success.TButton',
            command=self.complete_sale
        ).pack(side='left', padx=2, fill='x', expand=True)

    def create_recommendations_panel(self, parent):
        """Create recommendations panel (right side)."""
        # Title
        title = ttk.Label(parent, text="Recomendaciones", style='Subtitle.TLabel')
        title.pack(pady=(0, 10))

        # Status label
        self.status_label = ttk.Label(
            parent,
            text="Esperando productos...",
            style='Empty.TLabel'
        )
        self.status_label.pack(pady=5)

        # Canvas with scrollbar for recommendations
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(canvas_frame)
        scrollbar.pack(side='right', fill='y')

        self.recommendations_canvas = tk.Canvas(
            canvas_frame,
            bg=COLORS['white'],
            yscrollcommand=scrollbar.set,
            highlightthickness=0
        )
        self.recommendations_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.recommendations_canvas.yview)

        # Inner frame for recommendations
        self.rec_inner_frame = ttk.Frame(self.recommendations_canvas)
        self.canvas_window = self.recommendations_canvas.create_window(
            (0, 0),
            window=self.rec_inner_frame,
            anchor='nw'
        )

        # Configure scroll region
        self.rec_inner_frame.bind('<Configure>', self._on_frame_configure)
        self.recommendations_canvas.bind('<Configure>', self._on_canvas_configure)

    def create_toolbar(self, parent):
        """Create bottom toolbar."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(side='bottom', fill='x', pady=(10, 0))

        # Simulator button
        ttk.Button(
            toolbar,
            text="Abrir Simulador",
            command=self.open_simulator
        ).pack(side='left', padx=5)

        # Cache stats button
        ttk.Button(
            toolbar,
            text="Ver Estadísticas",
            command=self.show_stats
        ).pack(side='left', padx=5)

        # API status indicator
        api_status = "API: ✓ Conectada" if self.api_available else "API: ✗ No disponible"
        api_color = COLORS['success'] if self.api_available else COLORS['error']
        ttk.Label(
            toolbar,
            text=api_status,
            foreground=api_color
        ).pack(side='right', padx=5)

    def on_barcode_scanned(self, barcode: str):
        """
        Callback when barcode is scanned.

        Args:
            barcode: EAN-13 barcode string
        """
        self.logger.info(f"Barcode scanned: {barcode}")

        # Look up product in database
        product = self.db.get_product_by_ean(barcode)

        if not product:
            messagebox.showwarning(
                "Producto no encontrado",
                f"No se encontró ningún producto con el código {barcode}"
            )
            return

        # Add to cart
        self.add_to_cart(product)

    def add_to_cart(self, product: Product):
        """
        Add product to cart.

        Args:
            product: Product dataclass from database
        """
        # Check if already in cart
        product_id = product.id

        if product_id in self.cart_counts:
            # Increment quantity
            self.cart_counts[product_id] += 1
        else:
            # Add new item
            self.cart.append(product)
            self.cart_counts[product_id] = 1

        self.update_cart_display()
        self.schedule_recommendation_update()

        self.logger.info(f"Added to cart: {product.name}")

    def update_cart_display(self):
        """Update cart treeview and total."""
        # Clear current items
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)

        # Add items
        total = 0.0
        for product in self.cart:
            product_id = product.id
            quantity = self.cart_counts[product_id]
            price = product.price
            subtotal = price * quantity

            self.cart_tree.insert('', 'end', values=(
                quantity,
                product.name,
                f"€{price:.2f}",
                f"€{subtotal:.2f}"
            ))

            total += subtotal

        # Update total
        self.total_label.config(text=f"€{total:.2f}")

    def schedule_recommendation_update(self):
        """Schedule recommendation update with debounce."""
        # Cancel previous timer
        if self.debounce_timer:
            self.root.after_cancel(self.debounce_timer)

        # Schedule new timer
        delay_ms = int(config.DEBOUNCE_DELAY * 1000)
        self.debounce_timer = self.root.after(delay_ms, self.update_recommendations)

        self.logger.debug(f"Scheduled recommendation update in {config.DEBOUNCE_DELAY}s")

    def update_recommendations(self):
        """Update recommendations (triggers API call in thread)."""
        if not self.cart:
            self.clear_recommendations()
            self.status_label.config(
                text="Agregue productos al carrito",
                style='Empty.TLabel'
            )
            return

        if not self.api_available:
            self.status_label.config(
                text="API no disponible",
                style='Error.TLabel'
            )
            return

        # Show loading state
        self.status_label.config(
            text="Cargando recomendaciones...",
            style='Loading.TLabel'
        )

        # Start worker thread
        thread = threading.Thread(target=self._fetch_recommendations, daemon=True)
        thread.start()

    def _fetch_recommendations(self):
        """Worker thread: fetch recommendations from API."""
        try:
            # Prepare cart items
            cart_items = []
            for product in self.cart:
                cart_items.append({
                    'name': product.name,
                    'category': product.category,
                    'active_ingredient': product.active_ingredient,
                    'price': product.price
                })

            # Call API
            result = self.claude_client.get_recommendations(cart_items)

            # Update UI on main thread
            self.root.after(0, self._display_recommendations, result)

        except Exception as e:
            self.logger.error(f"Error fetching recommendations: {e}")
            self.root.after(0, self._show_error, str(e))

    def _display_recommendations(self, result: Optional[Dict]):
        """
        Display recommendations in UI (main thread).

        Args:
            result: Result from ClaudeClient
        """
        if not result or 'recommendations' not in result:
            self._show_error("No se pudieron obtener recomendaciones")
            return

        recommendations = result['recommendations']
        source = result.get('source', 'unknown')

        self.logger.info(f"Displaying {len(recommendations)} recommendations from {source}")

        # Clear previous recommendations
        self.clear_recommendations()

        # Update status
        cache_indicator = " (caché)" if source == 'cache' else ""
        self.status_label.config(
            text=f"{len(recommendations)} recomendaciones{cache_indicator}",
            style='Success.TLabel'
        )

        # Create recommendation cards
        for rec in recommendations:
            self._create_recommendation_card(rec)

        # Update scroll region
        self.rec_inner_frame.update_idletasks()
        self.recommendations_canvas.config(
            scrollregion=self.recommendations_canvas.bbox('all')
        )

    def _create_recommendation_card(self, rec: Dict):
        """
        Create visual card for a recommendation.

        Args:
            rec: Recommendation dict with product_name, category, reason, priority
        """
        priority = rec.get('priority', 'low')
        frame_style = get_priority_frame_style(priority)

        card = ttk.Frame(self.rec_inner_frame, style=frame_style, padding=10)
        card.pack(fill='x', pady=5, padx=5)

        # Priority indicator
        priority_color = get_priority_color(priority)
        priority_label = ttk.Label(
            card,
            text=f"● {priority.upper()}",
            foreground=priority_color,
            font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold')
        )
        priority_label.pack(anchor='w')

        # Product name
        name_label = ttk.Label(
            card,
            text=rec['product_name'],
            font=(config.FONT_FAMILY, config.FONT_SIZE + 1, 'bold')
        )
        name_label.pack(anchor='w', pady=(5, 2))

        # Category
        category_label = ttk.Label(
            card,
            text=f"Categoría: {rec['category']}",
            font=(config.FONT_FAMILY, config.FONT_SIZE - 1)
        )
        category_label.pack(anchor='w')

        # Reason
        reason_label = ttk.Label(
            card,
            text=rec['reason'],
            font=(config.FONT_FAMILY, config.FONT_SIZE),
            wraplength=400
        )
        reason_label.pack(anchor='w', pady=(5, 0))

        # Price if available
        if 'estimated_price' in rec:
            price_label = ttk.Label(
                card,
                text=f"Precio aprox: €{rec['estimated_price']}",
                font=(config.FONT_FAMILY, config.FONT_SIZE, 'bold'),
                foreground=COLORS['success']
            )
            price_label.pack(anchor='w', pady=(5, 0))

    def _show_error(self, message: str):
        """Show error in recommendations panel."""
        self.clear_recommendations()
        self.status_label.config(
            text=f"Error: {message}",
            style='Error.TLabel'
        )
        self.logger.error(f"Recommendation error: {message}")

    def clear_recommendations(self):
        """Clear all recommendation cards."""
        for widget in self.rec_inner_frame.winfo_children():
            widget.destroy()

    def remove_item(self):
        """Remove selected item from cart."""
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showinfo("Información", "Seleccione un producto para eliminar")
            return

        # Get selected index
        item_id = selection[0]
        index = self.cart_tree.index(item_id)

        # Remove from cart
        product = self.cart[index]
        product_id = product.id

        if self.cart_counts[product_id] > 1:
            # Decrement quantity
            self.cart_counts[product_id] -= 1
        else:
            # Remove completely
            del self.cart_counts[product_id]
            self.cart.pop(index)

        self.update_cart_display()
        self.schedule_recommendation_update()

        self.logger.info(f"Removed from cart: {product.name}")

    def new_sale(self):
        """Clear cart for new sale."""
        if self.cart and not messagebox.askyesno(
            "Nueva Compra",
            "¿Desea limpiar el carrito actual?"
        ):
            return

        self.cart.clear()
        self.cart_counts.clear()
        self.update_cart_display()
        self.clear_recommendations()
        self.status_label.config(
            text="Carrito limpio - agregue productos",
            style='Empty.TLabel'
        )

        self.logger.info("Cart cleared for new sale")

    def complete_sale(self):
        """Complete and save current sale."""
        if not self.cart:
            messagebox.showinfo("Información", "El carrito está vacío")
            return

        # Calculate total
        total = sum(
            p['price'] * self.cart_counts[p['id']]
            for p in self.cart
        )

        # Confirm
        if not messagebox.askyesno(
            "Finalizar Venta",
            f"¿Finalizar venta por €{total:.2f}?"
        ):
            return

        # Save to database
        try:
            sale_id = self.db.create_sale(total, len(self.cart))

            for product in self.cart:
                quantity = self.cart_counts[product.id]
                subtotal = product.price * quantity

                self.db.add_sale_item(
                    sale_id,
                    product.id,
                    quantity,
                    product.price,
                    subtotal
                )

            messagebox.showinfo(
                "Venta Completada",
                f"Venta #{sale_id} guardada correctamente"
            )

            # Clear cart
            self.new_sale()

            self.logger.info(f"Sale completed: #{sale_id}, total: €{total:.2f}")

        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar venta: {e}")
            self.logger.error(f"Error completing sale: {e}")

    def open_simulator(self):
        """Open barcode simulator window."""
        if self.simulator:
            messagebox.showinfo("Información", "El simulador ya está abierto")
            return

        # Load sample products
        products = self.db.get_all_products()
        sample_products = [
            {'ean': p.ean, 'name': p.name}
            for p in products[:20]  # First 20 products
        ]

        self.simulator = BarcodeSimulator(
            callback=self.on_barcode_scanned,
            sample_products=sample_products
        )

        # Start simulator (creates root window)
        self.simulator.start()

        # Cleanup on close
        def on_simulator_close():
            self.simulator = None

        self.simulator.root.protocol("WM_DELETE_WINDOW", on_simulator_close)

    def show_stats(self):
        """Show cache and API statistics."""
        if not self.api_available:
            messagebox.showinfo("Información", "API no disponible")
            return

        stats = self.claude_client.get_stats()
        cache_stats = stats.get('cache_stats', {})

        stats_window = tk.Toplevel(self.root)
        stats_window.title("Estadísticas")
        stats_window.geometry("400x300")

        text = scrolledtext.ScrolledText(stats_window, wrap='word', font=('Courier', 10))
        text.pack(fill='both', expand=True, padx=10, pady=10)

        # Format stats
        text.insert('end', "=== ESTADÍSTICAS DEL SISTEMA ===\n\n")
        text.insert('end', "API CLIENT:\n")
        text.insert('end', f"  Llamadas API: {stats['api_calls']}\n")
        text.insert('end', f"  Errores API: {stats['api_errors']}\n")
        text.insert('end', f"  Cache Hits: {stats['cache_hits']}\n\n")

        if cache_stats:
            text.insert('end', "CACHE:\n")
            text.insert('end', f"  Tamaño: {cache_stats['size']}/{cache_stats['max_size']}\n")
            text.insert('end', f"  Hits: {cache_stats['hits']}\n")
            text.insert('end', f"  Misses: {cache_stats['misses']}\n")
            text.insert('end', f"  Hit Rate: {cache_stats['hit_rate']:.1f}%\n")
            text.insert('end', f"  Evictions: {cache_stats['evictions']}\n")
            text.insert('end', f"  Expirations: {cache_stats['expirations']}\n")

        text.config(state='disabled')

    def _on_frame_configure(self, event=None):
        """Update scroll region when frame size changes."""
        self.recommendations_canvas.configure(
            scrollregion=self.recommendations_canvas.bbox('all')
        )

    def _on_canvas_configure(self, event):
        """Update frame width when canvas resizes."""
        canvas_width = event.width
        self.recommendations_canvas.itemconfig(
            self.canvas_window,
            width=canvas_width
        )
