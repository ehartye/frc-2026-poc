"""Six cut plates supporting the two original intake ramps, in robot coordinates (mm)."""

def parts():
    rows = {}
    for side, sign in (("left",1),("right",-1)):
        cheek=side+" intake foundation cheek"
        # The occupied electronics deck covers the rail top. Fit the heel to the
        # exposed forward vertical rail face; leave two mm below the deck edge.
        contour=[(141.7,98),(141.7,120),(169,120),(174,138),(279,115),(314.6,114.8),(337,114.8),
                 (337,64),(319,44),(299,44),(280,54),(225,54),(210,74),
                 (205,90),(167,106)]
        rows[cheek]={"points":[[x,144*sign,z] for x,z in contour],
                     "delta":[0,6*sign,0],"material":"Aluminum 6061","role":"structure",
                     "parents":["front deck crossmember",side+" front return"]}
        for label, x in (("aft",218),("forward",317)):
            z=48-(x-213)*33/124
            high=82 if label=="aft" else 72
            profile=([(74,z-2),(122,19),(137,19),(144,high-15),(144,high),
                      (136,28),(122,28),(74,z+2)] if label=="aft" else
                     [(74,z-2),(144,high-15),(144,high),(74,z+2)])
            rows[side+" ramp bridge "+label]={
                "points":[[x-4,sign*y,h] for y,h in profile], "delta":[8,0,0],
                "material":"Aluminum 6061","role":"structure",
                "parents":[side+" intake ramp",cheek]}
    return rows
