"""Inicia o Painel de Gestão Integrada. Ex.: python main.py --carousel --fullscreen"""
import argparse
from painel import DashboardApp


def main():
    parser = argparse.ArgumentParser(description='Painel industrial de Gestão Integrada')
    presentation = parser.add_mutually_exclusive_group()
    presentation.add_argument('--carousel', action='store_true', help='Abrir carrossel ANDON')
    presentation.add_argument('--chart-carousel', action='store_true', help='Abrir carrossel de gráficos')
    presentation.add_argument('--custom-carousel', action='store_true', help='Abrir layouts personalizados')
    parser.add_argument('--fullscreen', action='store_true', help='Iniciar em tela cheia')
    args = parser.parse_args()
    app = DashboardApp()
    if args.carousel:
        app.after(100, app.open_carousel)
    if args.chart_carousel:
        app.after(100, app.open_chart_carousel)
    if args.custom_carousel:
        app.after(100, app.open_custom_carousel)
    if args.fullscreen:
        app.after(180, app.toggle_fullscreen)
    app.mainloop()


if __name__ == '__main__':
    main()
