    public _spritePalette
    public _shipSprite
    public _leftShip
    public _rightShip
    public _missile

    section rodata_compiler

; Sprite palette data
_spritePalette:
    binary "ship.pal"

; Ship sprite tiles
_shipSprite:
    binary "ship.tiles"

; Left-facing ship sprite tiles
_leftShip:
    binary "left_ship.tiles"

; Right-facing ship sprite tiles
_rightShip:
    binary "right_ship.tiles"

; Missile sprite tiles
_missile:
    binary "missile.tiles"
