"""Cut-list based support stock. 6061-T6 is the procurement temper before welding."""

from shop import article, rect, stock, drill

SECTION = {
    "perimeter": ("Online Metals 18003", 25.4, 50.8, 3.175),
    "cross": ("Online Metals 18014", 25.4, 25.4, 3.175),
    "hopper": ("Online Metals 18011", 19.05, 19.05, 1.5748),
}


def tube(start, end, width, height, wall):
    axis = next(i for i in range(3) if start[i] != end[i])
    cross = [i for i in range(3) if i != axis]
    lo = list(start)
    hi = list(end)
    for j, h in zip(cross, (width, height)):
        lo[j] -= h / 2
        hi[j] += h / 2
    a = lo.copy()
    b = hi.copy()
    a[axis] -= 1
    b[axis] += 1
    for j in cross:
        a[j] += wall
        b[j] -= wall
    return [stock(rect(lo, hi)), drill(rect(a, b))]


def build():
    articles = {}

    def member(name, section, start, end, parents, method):
        sku, width, height, wall = SECTION[section]
        features = tube(start, end, width, height, wall)
        row = article(
            name,
            "structure",
            "Aluminum 6061",
            features,
            parent=parents,
            connection=method,
            purchase=sku,
        )
        row["stock"] = {
            "source": sku,
            "grade": "6061-T6",
            "widthMm": width,
            "heightMm": height,
            "wallMm": wall,
            "cutLengthMm": sum(abs(b - a) for a, b in zip(start, end)),
        }
        articles[name] = row

    member(
        "rear perimeter tube",
        "perimeter",
        [-327.3, -314.6, 89.4],
        [-327.3, 314.6, 89.4],
        "left perimeter tube; right perimeter tube",
        "Join both end faces to side-rail inner faces. Square and tack fixture before perimeter welding.",
    )
    for sg, side in ((-1, "right"), (1, "left")):
        y = 327.3 * sg
        member(
            side + " perimeter tube",
            "perimeter",
            [-340, y, 89.4],
            [340, y, 89.4],
            "rear perimeter tube; " + side + " front return",
            "Continuous rail. End-return welds transfer reaction at each welded cross joint.",
        )
        y0, y1 = sorted([150 * sg, 314.6 * sg])
        member(
            side + " front return",
            "perimeter",
            [327.3, y0, 89.4],
            [327.3, y1, 89.4],
            side + " perimeter tube",
            "Outside end butts the side-rail inner face. Tube ends face square for proper joint fit.",
        )
        sy = 294 * sg
        member(
            side + " floor sill",
            "hopper",
            [-330, sy, 220.475],
            [150, sy, 220.475],
            "rear " + side + " hopper post; front " + side + " hopper post",
            "Underside of sill rests on both posts at Z210.95. Weld before installing hopper floor.",
        )
        for x, end in ((-151, "rear"), (129, "front")):
            member(
                end + " " + side + " hopper post",
                "hopper",
                [x, sy, 122],
                [x, sy, 210.95],
                end + " deck crossmember",
                "Square cut; 1.5 mm fillet at each foot face. Weld aboard the bare crossmember before installing module, deck or hopper. Verify fit and heat distortion.",
            )
    for x, end in ((-151, "rear"), (129, "front")):
        member(
            end + " deck crossmember",
            "cross",
            [x, -308.25, 109.3],
            [x, 308.25, 109.3],
            end
            + " left crossmember backing plate; "
            + end
            + " right crossmember backing plate",
            "616.50 mm cut between two backing plates. All four tube walls butt the flat plates. Fillet-weld accessible external end contour before adding the hopper posts.",
        )
        for sg, side in ((-1, "right"), (1, "left")):
            name = end + " " + side + " crossmember backing plate"
            lo, hi = sorted([sg * 308.25, sg * 314.60])
            articles[name] = article(
                name,
                "structure",
                "Aluminum 6061",
                [stock(rect([x - 25.4, lo, 65.5], [x + 25.4, hi, 129.0]))],
                parent=side + " perimeter tube",
                connection="6.35 x 50.8 flat bar, 63.50 cut. Weld vertical edges against side rail up to Z114.8 and the bottom edge before setting the crossmember. Top 14.2 mm cantilevers. Welded joint strength requires separate load qualification.",
                purchase="Online Metals 1145, 6061-T6511 extruded flat bar",
            )
            articles[name]["stock"] = {
                "source": "Online Metals 1145",
                "grade": "6061-T6511",
                "widthMm": 50.8,
                "thicknessMm": 6.35,
                "cutLengthMm": 63.5,
            }
    return articles
