"""Original four-faced 1780 print in millimetres. Local u increases rightward to each observer."""

INK_MM = 0.12
HEIGHT_MM = 100
STROKE_MM = 13
WIDTHS = [23, 42, 42, 43]
GAP_MM = 5
FACES = {
    "left": ("left blue side bumper", (0, 416), (-1, 0), (0, 1)),
    "right": ("right blue side bumper", (0, -416), (1, 0), (0, -1)),
    "rear": ("rear blue bumper", (-416, 0), (0, -1), (-1, 0)),
    "front": ("left blue front bumper", (416, 245), (0, 1), (1, 0)),
}
COVERS = [*dict.fromkeys(r[0] for r in FACES.values()), "right blue front bumper"]


def polygon(x0, y0, x1, y1, cut):
    return [
        (x0 + cut, y0),
        (x1 - cut, y0),
        (x1, y0 + cut),
        (x1, y1 - cut),
        (x1 - cut, y1),
        (x0 + cut, y1),
        (x0, y1 - cut),
        (x0, y0 + cut),
    ]


def glyphs():
    outlines = [
        [[(0, 80), (0, 94), (10, 100), (23, 100), (23, 0), (10, 0), (10, 85)]],
        [[(0, 100), (42, 100), (42, 87), (19, 0), (5.2, 0), (28.2, 87), (0, 87)]],
        [
            polygon(0, 0, 42, 100, 5),
            polygon(13, 13, 29, 43.5, 2.5),
            polygon(13, 56.5, 29, 87, 2.5),
        ],
        [polygon(0, 0, 43, 100, 5), polygon(13, 13, 30, 87, 3)],
    ]
    total = sum(WIDTHS) + 3 * GAP_MM
    for face, (panel, center, right, normal) in FACES.items():
        start = -total / 2
        for digit, width, rings in zip("1780", WIDTHS, outlines):
            loops = [
                [
                    [
                        center[0] + right[0] * (start + x),
                        center[1] + right[1] * (start + x),
                        58 + z,
                    ]
                    for x, z in ring
                ]
                for ring in rings
            ]
            yield {
                "name": f"{face} white 1780 digit {digit}",
                "sourcePanel": panel,
                "face": face,
                "digit": digit,
                "loops": loops,
                "normal": [*normal, 0],
                "depthMm": INK_MM,
            }
            start += width + GAP_MM
