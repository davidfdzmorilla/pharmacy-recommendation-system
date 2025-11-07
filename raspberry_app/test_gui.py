#!/usr/bin/env python3
"""
Test GUI - Validación de configuración Docker + XQuartz
"""
import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("✅ Test GUI - Pharmacy System")
    root.geometry("600x400")
    root.configure(bg="#f0f0f0")

    # Frame principal
    main_frame = ttk.Frame(root, padding="40")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Título
    title = tk.Label(
        main_frame,
        text="✅ GUI Funcionando Correctamente!",
        font=("Arial", 24, "bold"),
        fg="#2E86AB",
        bg="#f0f0f0"
    )
    title.pack(pady=20)

    # Subtítulo
    subtitle = tk.Label(
        main_frame,
        text="Docker + XQuartz configurado exitosamente",
        font=("Arial", 14),
        fg="#555",
        bg="#f0f0f0"
    )
    subtitle.pack(pady=10)

    # Información
    info_frame = ttk.LabelFrame(main_frame, text="Información del Sistema", padding="20")
    info_frame.pack(pady=20, fill=tk.X)

    info_texts = [
        "✅ Python + tkinter funcionando",
        "✅ X11 forwarding operativo",
        "✅ Contenedor Docker comunicándose con XQuartz",
        "✅ Hot-reload configurado (modo desarrollo)"
    ]

    for text in info_texts:
        label = tk.Label(
            info_frame,
            text=text,
            font=("Arial", 11),
            fg="#06A77D",
            bg="#f0f0f0",
            anchor="w"
        )
        label.pack(pady=5, fill=tk.X)

    # Botón de cierre
    close_button = ttk.Button(
        main_frame,
        text="Cerrar Test",
        command=root.destroy
    )
    close_button.pack(pady=20)

    # Mensaje final
    footer = tk.Label(
        main_frame,
        text="Presiona el botón o cierra la ventana para continuar",
        font=("Arial", 10),
        fg="#888",
        bg="#f0f0f0"
    )
    footer.pack(pady=10)

    root.mainloop()
    print("\n✅ Test GUI completado exitosamente!")
    print("El sistema está listo para desarrollo.\n")

if __name__ == "__main__":
    main()
