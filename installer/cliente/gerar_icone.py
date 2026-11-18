"""Gera cortex.ico (quadrado azul com "CX", o mesmo desenho do manifest do app).

Uso: python gerar_icone.py <destino.ico>
"""

import sys

from PIL import Image, ImageDraw, ImageFont


def desenhar(lado: int = 256) -> Image.Image:
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, lado - 1, lado - 1), radius=int(lado * 0.2), fill=(37, 99, 235, 255))
    fonte = None
    for nome in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            fonte = ImageFont.truetype(nome, int(lado * 0.45))
            break
        except OSError:
            continue
    fonte = fonte or ImageFont.load_default()
    d.text((lado / 2, lado / 2), "CX", font=fonte, fill="white", anchor="mm")
    return img


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else "cortex.ico"
    desenhar().save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ícone gerado:", destino)
