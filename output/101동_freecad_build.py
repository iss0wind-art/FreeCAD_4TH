"""FreeCAD 3D Model — 101동 (generated)"""
import FreeCAD, Part
from FreeCAD import Vector
doc = FreeCAD.newDocument("101동")

# B1F: SL = -5600mm
# B2F: SL = -9050mm
# 5F: SL = 11790mm
# 6F: SL = 14620mm
# 7F: SL = 17450mm
# 8F: SL = 20280mm
# 9F: SL = 23110mm
# 10F: SL = 25940mm
# 11F: SL = 28770mm
# 12F: SL = 31600mm
# 2F: SL = 3300mm
# 13F: SL = 34430mm
# 1F: SL = 370mm
# 14F: SL = 37260mm
# 15F: SL = 40090mm
# Roof: SL = 43020mm
# 3F: SL = 6130mm
# 4F: SL = 8960mm

# COLUMNS: RC=5272 PC=0
rc_group = doc.addObject('App::DocumentObjectGroup', 'Columns_RC')
pc_group = doc.addObject('App::DocumentObjectGroup', 'Columns_PC')

col = Part.makeBox(800.0000000037253, 400.00000000884756, 2830, Vector(182083.97106702498, 2209104.306003605, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_0')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0000000079308, 800.0000000037253, 2830, Vector(96440.86942494393, 2373604.3059288473, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_1')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.00000000836735, 800.0000000037253, 2830, Vector(96440.86942484009, 2381404.306003527, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_2')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558070019819, 873.005339264404, 2830, Vector(104953.82160628459, 2303442.8085898105, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_3')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0000000079308, 800.0000000037253, 2830, Vector(96440.86942494719, 2365104.3060037517, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_4')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.00000000788714, 800.000000002794, 2830, Vector(88240.8694249528, 2365104.3060037885, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_5')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0000000079017, 800.000000002794, 2830, Vector(88240.86942494998, 2356604.3060037885, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_6')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0000000079308, 800.0000000037253, 2830, Vector(96440.8694249444, 2356604.3060037517, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_7')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.000000008411, 800.000000002794, 2830, Vector(88240.8692543829, 2348204.3060037377, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_8')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.00000000839646, 800.000000002794, 2830, Vector(88240.8692543722, 2343904.306003568, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_9')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0000000083819, 800.0000000037253, 2830, Vector(129040.86942493415, 2381404.306003882, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_10')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558070015162, 873.0053392639384, 2830, Vector(176225.17578505178, 2249482.0443854043, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_11')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558070015162, 873.0053392648697, 2830, Vector(158518.24114458414, 2307934.6411253028, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_12')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(873.0053392872214, 581.6558070820756, 2830, Vector(170128.2223867426, 2273496.994017763, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_13')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(873.0053392648697, 581.6558070015162, 2830, Vector(149738.31606854557, 2323447.987204458, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_14')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558070015162, 873.0053392639384, 2830, Vector(104097.24757301959, 2329612.9496082338, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_15')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.00000000791624, 800.0000000037253, 2830, Vector(123540.86942495557, 2373604.306003812, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_16')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0000000069849, 800.0000000037253, 2830, Vector(141890.86942493648, 2356604.3060038015, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_17')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-9926.767734985187, 2287865.6784219122, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_18')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-9876.767734985187, 2287715.6784219122, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_19')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-1926.7677349857113, 2287865.6784219197, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_20')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-1876.7677349857113, 2287715.6784219197, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_21')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(6173.232265015191, 2287865.6784219174, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_22')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(6223.232265015191, 2287715.6784219174, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_23')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(14273.232265014813, 2287865.6784219155, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_24')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(14323.232265014813, 2287715.6784219155, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_25')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(22373.23226501199, 2287865.6784219136, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_26')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(22423.23226501199, 2287715.6784219136, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_27')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(30473.232265014813, 2287865.6784219113, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_28')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(30523.232265014813, 2287715.6784219113, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_29')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-9926.767734982888, 2296265.678421895, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_30')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-9876.767734982888, 2296115.678421895, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_31')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-1926.767734983412, 2296265.6784219025, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_32')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-1876.767734983412, 2296115.6784219025, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_33')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(6173.232265017607, 2296265.6784219, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_34')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(6223.232265017607, 2296115.6784219, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_35')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(14273.232265017607, 2296265.6784218983, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_36')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(14323.232265017607, 2296115.6784218983, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_37')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(22373.232265014813, 2296265.6784218964, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_38')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(22423.232265014813, 2296115.6784218964, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_39')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(30473.232265017607, 2296265.678421894, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_40')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(30523.232265017607, 2296115.678421894, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_41')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-9926.7677349796, 2304865.678421902, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_42')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-9876.7677349796, 2304715.678421902, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_43')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-1926.76773496659, 2335865.678421911, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_44')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-1876.76773496659, 2335715.678421911, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_45')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(6473.232264949591, 2335865.6784219006, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_46')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(6523.232264949591, 2335715.6784219006, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_47')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(15073.232265042694, 2335865.6784219067, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_48')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(15123.232265042694, 2335715.6784219067, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_49')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(-1926.7677349628939, 2344365.678421908, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_50')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(-1876.7677349628939, 2344215.678421908, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_51')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(6473.232264953287, 2344365.678421898, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_52')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(6523.232264953287, 2344215.678421898, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_53')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(59643.0272638966, 2292321.881858313, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_54')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(59602.199360401544, 2292135.379188682, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_55')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(57610.88334071651, 2300472.3659589924, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_56')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(57570.055437221454, 2300285.863289362, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_57')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(49654.4583852879, 2298488.6064149337, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_58')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(49613.63048179285, 2298302.103745303, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_59')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(65567.308296146, 2302456.125503052, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_60')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(65526.48039265095, 2302269.6228334215, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_61')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(71097.9939358943, 2303835.080308069, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_62')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(71057.16603239924, 2303648.577638438, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_63')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(79054.4188913234, 2305818.839852118, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_64')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(79013.59098782834, 2305632.3371824874, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_65')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(87010.8438467506, 2307802.599396174, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_66')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(581.6558069901366, 873.0053392606787, 2830, Vector(86970.01594325555, 2307616.0967265433, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_67')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(37648.095067304705, 2338182.103168891, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_68')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(37631.6742456355, 2338003.4504321525, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_69')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(45920.480192657706, 2339640.747861009, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_70')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(45904.0593709885, 2339462.0951242708, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_71')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(54389.8268686138, 2341134.1221886543, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_72')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(54373.4060469446, 2340955.469451916, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_73')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(36189.45037490511, 2346454.4882941875, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_74')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(36173.0295532359, 2346275.835557449, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_75')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(44461.83550025811, 2347913.132986306, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_76')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(44445.4146785889, 2347734.480249568, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_77')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(52931.18217621429, 2349406.5073139514, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_78')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(52914.76135454509, 2349227.854577213, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_79')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999997, 499.9999999999997, 2830, Vector(61006.605750963194, 2350830.422370543, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_80')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(532.8416433384264, 857.3054734766483, 2830, Vector(60990.18492929399, 2350651.7696338044, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_81')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999982, 499.9999999999982, 2830, Vector(59582.6906940933, 2358905.8459452465, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_82')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(857.3054734765319, 532.8416433380917, 2830, Vector(59404.03795735509, 2358889.4251235775, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_83')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999982, 499.9999999999982, 2830, Vector(51507.267119344906, 2357481.930888654, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_84')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(857.3054734765319, 532.8416433380917, 2830, Vector(51328.6143826067, 2357465.510066985, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_85')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999982, 499.9999999999982, 2830, Vector(43037.92044338831, 2355988.5565610095, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_86')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(857.3054734765319, 532.8416433380917, 2830, Vector(42859.267706650106, 2355972.1357393404, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_87')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(499.9999999999982, 499.9999999999982, 2830, Vector(34765.53531803531, 2354529.9118688907, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_88')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(857.3054734765319, 532.8416433380917, 2830, Vector(34586.882581297104, 2354513.4910472217, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_89')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(122233.97106701008, 2145114.306003627, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_90')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(122283.97106701008, 2144964.306003627, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_91')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(114133.97106701799, 2145114.306003631, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_92')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(800.0, 400.0, 2830, Vector(113983.97106701805, 2145164.306003631, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_93')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(122233.97106701194, 2153414.306003627, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_94')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(122283.97106701194, 2153264.306003627, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_95')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(114133.97106701985, 2153314.306003631, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_96')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(800.0, 400.0, 2830, Vector(113983.97106701991, 2153364.306003631, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_97')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(500.0, 500.0, 2830, Vector(122233.97106701473, 2161514.3060036385, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_98')
obj.Shape = col
rc_group.addObject(obj)

col = Part.makeBox(400.0, 800.0, 2830, Vector(122283.97106701473, 2161364.3060036385, -5600))
obj = doc.addObject('Part::Feature', 'C_RC_99')
obj.Shape = col
rc_group.addObject(obj)

# BEAMS: RC=5458 PC=0
beam_rc_g = doc.addObject('App::DocumentObjectGroup', 'Beams_RC')
beam_pc_g = doc.addObject('App::DocumentObjectGroup', 'Beams_PC')

p1 = Vector(297973.9805179615, 2119259.2930825246, -5600)
p2 = Vector(297973.980517961, 2118119.2930825246, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(297773.9805179615, 2118909.2930825246, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_0')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(297773.9805179615, 2119259.2930825246, -5600)
p2 = Vector(297773.980517961, 2118119.2930825246, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(297573.9805179615, 2118909.2930825246, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_1')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(295973.9805179573, 2117474.2930825227, -5600)
p2 = Vector(295973.9805179572, 2116304.305903955, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(295773.9805179573, 2117124.2930825227, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_2')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(295773.9805179573, 2117474.2930825227, -5600)
p2 = Vector(295773.9805179572, 2116304.305903955, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(295573.9805179573, 2117124.2930825227, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_3')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(297772.8279547202, 2114374.3059039535, -5600)
p2 = Vector(299092.8279547203, 2114374.305903954, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(297572.8279547202, 2114024.3059039535, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_4')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(299092.8279547202, 2114124.305903953, -5600)
p2 = Vector(297772.8279547202, 2114124.3059039484, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(298892.8279547202, 2113774.305903953, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_5')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(291703.98051795916, 2114274.293082525, -5600)
p2 = Vector(291703.98051795916, 2113154.293082525, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(291503.98051795916, 2113924.293082525, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_6')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(291953.98051795823, 2114274.3059039577, -5600)
p2 = Vector(291953.98051795916, 2113154.3059039577, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(291753.98051795823, 2113924.3059039577, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_7')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(318913.5417939425, 2125767.8208923372, -5600)
p2 = Vector(318205.5110484317, 2124677.5491540018, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(318713.5417939425, 2125417.8208923372, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_8')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(314199.9916726334, 2128435.356245345, -5600)
p2 = Vector(315156.07612009736, 2127814.4677454364, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(313999.9916726334, 2128085.356245345, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_9')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(315265.00392709946, 2127982.2018590276, -5600)
p2 = Vector(314308.91947963455, 2128603.0903589344, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(315065.00392709946, 2127632.2018590276, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_10')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(314765.10063767765, 2130453.0967781264, -5600)
p2 = Vector(315747.1500221679, 2129815.3464509547, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(314565.10063767765, 2130103.0967781264, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_11')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(314874.02844467893, 2130620.8308917144, -5600)
p2 = Vector(315856.07782916917, 2129983.080564544, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(314674.02844467893, 2130270.8308917144, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_12')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(317745.7526844269, 2131414.88150799, -5600)
p2 = Vector(318685.0637205254, 2130804.8857887727, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(317545.7526844269, 2131064.88150799, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_13')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(324968.7356610081, 2105430.3023436945, -5600)
p2 = Vector(325867.0679200973, 2106132.1564255944, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(324768.7356610081, 2105080.3023436945, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_14')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(325091.86795607285, 2105272.700192974, -5600)
p2 = Vector(325990.2002151809, 2105974.554274849, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(324891.86795607285, 2104922.700192974, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_15')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(327714.0298868368, 2104783.3211897174, -5600)
p2 = Vector(326792.77922216925, 2104063.561287001, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(327514.0298868368, 2104433.3211897174, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_16')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(327590.89759177394, 2104940.92334044, -5600)
p2 = Vector(326669.6469271266, 2104221.163437693, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(327390.89759177394, 2104590.92334044, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_17')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(326648.7836114659, 2101121.1489664437, -5600)
p2 = Vector(327531.3556555033, 2101810.6898188107, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(326448.7836114659, 2100771.1489664437, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_18')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(327684.11762720294, 2101613.675376316, -5600)
p2 = Vector(326801.54558316356, 2100924.134523949, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(327484.11762720294, 2101263.675376316, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_19')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(321207.2501990629, 2103723.3448650795, -5600)
p2 = Vector(322022.5379423992, 2102679.824140167, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(321007.2501990629, 2103373.3448650795, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_20')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(321017.5566976269, 2103561.5604983033, -5600)
p2 = Vector(321817.9166155516, 2102537.146518615, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(320817.5566976269, 2103211.5604983033, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_21')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(318714.4218394458, 2125920.222665507, -5600)
p2 = Vector(317995.8434064439, 2124813.708912754, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(318514.4218394458, 2125570.222665507, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_22')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(318820.4186592914, 2131015.07608697, -5600)
p2 = Vector(317881.1076231917, 2131625.0718061873, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(318620.4186592914, 2130665.07608697, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_23')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(543953.9805179556, 2114274.305903956, -5600)
p2 = Vector(543953.9805179568, 2113154.305903956, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(543753.9805179556, 2113924.305903956, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_24')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(543753.9805179568, 2113064.305903956, -5600)
p2 = Vector(543753.9805179565, 2114364.305903956, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(543553.9805179568, 2112714.305903956, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_25')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(547973.9805179562, 2117474.305903954, -5600)
p2 = Vector(547973.9805179562, 2116304.305903954, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(547773.9805179562, 2117124.305903954, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_26')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(547773.9805179562, 2117474.305903954, -5600)
p2 = Vector(547773.9805179562, 2116304.305903954, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(547573.9805179562, 2117124.305903954, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_27')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(549973.9805179602, 2119189.305903956, -5600)
p2 = Vector(549973.9805179599, 2118189.305903956, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(549773.9805179602, 2118839.305903956, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_28')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(549773.9805179599, 2118189.305903956, -5600)
p2 = Vector(549773.9805179602, 2119189.305903956, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(549573.9805179599, 2117839.305903956, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_29')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(549863.9805179556, 2114374.305903952, -5600)
p2 = Vector(550983.9805179557, 2114374.305903952, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(549663.9805179556, 2114024.305903952, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_30')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(551073.9805179557, 2114174.3059039516, -5600)
p2 = Vector(549773.9805179556, 2114174.3059039516, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(550873.9805179557, 2113824.3059039516, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_31')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(569745.7526844688, 2131414.8815078707, -5600)
p2 = Vector(570685.0637205724, 2130804.885788661, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(569545.7526844688, 2131064.8815078707, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_32')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(570869.471878689, 2130923.6023890995, -5600)
p2 = Vector(569779.2001403552, 2131631.6331346114, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(570669.471878689, 2130573.6023890995, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_33')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(566765.9054576929, 2130452.5741218952, -5600)
p2 = Vector(567747.1500221941, 2129815.346450934, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(566565.9054576929, 2130102.5741218952, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_34')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(566874.8332646964, 2130620.308235484, -5600)
p2 = Vector(567856.0778291961, 2129983.080564524, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(566674.8332646964, 2130270.308235484, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_35')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(566259.5184016125, 2128396.699135545, -5600)
p2 = Vector(567098.174000351, 2127852.069821655, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(566059.5184016125, 2128046.699135545, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_36')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(567207.1018073548, 2128019.8039352475, -5600)
p2 = Vector(566368.4312394023, 2128564.4429702545, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(567007.1018073548, 2127669.8039352475, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_37')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(570092.2408383627, 2124870.3440177785, -5600)
p2 = Vector(570702.2365575726, 2125809.655053882, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(569892.2408383627, 2124520.3440177785, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_38')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(570210.9574388018, 2124685.9358596615, -5600)
p2 = Vector(570918.9881843135, 2125776.2075979956, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(570010.9574388018, 2124335.9358596615, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_39')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(577024.6183308084, 2105473.9626703835, -5600)
p2 = Vector(577812.6290844136, 2106089.624145713, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(576824.6183308084, 2105123.9626703835, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_40')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(577147.7506258737, 2105316.360519662, -5600)
p2 = Vector(577935.7613794788, 2105932.021994992, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(576947.7506258737, 2104966.360519662, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_41')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(579591.6195088238, 2104941.487363853, -5600)
p2 = Vector(578669.6469271269, 2104221.163437692, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(579391.6195088238, 2104591.487363853, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_42')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(579714.7518038874, 2104783.8852131316, -5600)
p2 = Vector(578792.7792221691, 2104063.5612870003, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(579514.7518038874, 2104433.8852131316, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_43')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(579725.408918385, 2101708.4972008755, -5600)
p2 = Vector(578700.9949386971, 2100908.1372829513, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(579525.408918385, 2101358.4972008755, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_44')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(578648.7836114566, 2101121.148966451, -5600)
p2 = Vector(579531.3556554955, 2101810.6898188167, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(578448.7836114566, 2100771.148966451, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_45')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(573230.568381113, 2103613.771825549, -5600)
p2 = Vector(573920.1092334773, 2102731.199781509, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(573030.568381113, 2103263.771825549, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_46')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(573817.916615537, 2102537.1465186207, -5600)
p2 = Vector(573017.5566976124, 2103561.5604983084, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(573617.916615537, 2102187.1465186207, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_47')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(673773.980517958, 2117474.305903955, -5600)
p2 = Vector(673773.980517958, 2116304.305903955, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(673573.980517958, 2117124.305903955, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_48')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(673973.9805179565, 2117474.305903955, -5600)
p2 = Vector(673973.9805179565, 2116304.3059037435, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(673773.9805179565, 2117124.305903955, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_49')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(675973.9805179607, 2119189.305903949, -5600)
p2 = Vector(675973.9805179603, 2118189.305903949, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(675773.9805179607, 2118839.305903949, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_50')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(675773.9805179621, 2118189.305903949, -5600)
p2 = Vector(675773.9805179621, 2119189.305903949, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(675573.9805179621, 2117839.305903949, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_51')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(675863.9805179551, 2114374.305903954, -5600)
p2 = Vector(676983.9805179553, 2114374.305903954, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(675663.9805179551, 2114024.305903954, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_52')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(677073.9805179553, 2114174.3059039535, -5600)
p2 = Vector(675773.9805179551, 2114174.3059039516, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(676873.9805179553, 2113824.3059039535, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_53')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(669753.9805179569, 2114364.3059039568, -5600)
p2 = Vector(669753.9805179574, 2113064.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(669553.9805179569, 2114014.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_54')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(669953.9805179574, 2113154.3059039568, -5600)
p2 = Vector(669953.9805179574, 2114274.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(669753.9805179574, 2112804.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_55')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(692259.5034324009, 2128396.7088566655, -5600)
p2 = Vector(693098.1740003517, 2127852.0698216553, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(692059.5034324009, 2128046.7088566655, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_56')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(693207.1018073555, 2128019.8039352484, -5600)
p2 = Vector(692368.4312394036, 2128564.442970253, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(693007.1018073555, 2127669.8039352484, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_57')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(692765.9054576947, 2130452.574121898, -5600)
p2 = Vector(693747.1500221945, 2129815.346450935, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(692565.9054576947, 2130102.574121898, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_58')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(692874.83381535, 2130620.3090834166, -5600)
p2 = Vector(693856.0783798501, 2129983.0814124565, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(692674.83381535, 2130270.3090834166, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_59')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(695745.7526844693, 2131414.881507872, -5600)
p2 = Vector(696685.0637205722, 2130804.8857886624, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(695545.7526844693, 2131064.881507872, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_60')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(695779.2001403553, 2131631.6331346123, -5600)
p2 = Vector(696869.4718786905, 2130923.6023891023, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(695579.2001403553, 2131281.6331346123, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_61')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(696702.2365575733, 2125809.6550538833, -5600)
p2 = Vector(696092.2408383635, 2124870.34401778, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(696502.2365575733, 2125459.6550538833, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_62')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(696210.9574388029, 2124685.9358596625, -5600)
p2 = Vector(696918.9881843143, 2125776.207597997, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(696010.9574388029, 2124335.9358596625, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_63')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(703024.6183308089, 2105473.9626703844, -5600)
p2 = Vector(703812.6290844149, 2106089.624145711, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(702824.6183308089, 2105123.9626703844, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_64')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(703147.7506258736, 2105316.360519663, -5600)
p2 = Vector(703935.7613794801, 2105932.02199499, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(702947.7506258736, 2104966.360519663, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_65')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(705591.6195088254, 2104941.487363853, -5600)
p2 = Vector(704669.646927106, 2104221.1634377204, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(705391.6195088254, 2104591.487363853, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_66')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(705714.7518038879, 2104783.8852131325, -5600)
p2 = Vector(704792.7792221697, 2104063.561287001, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(705514.7518038879, 2104433.8852131325, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_67')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(699230.5683811135, 2103613.7718255506, -5600)
p2 = Vector(699920.1092334783, 2102731.199781511, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(699030.5683811135, 2103263.7718255506, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_68')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(699817.9166155375, 2102537.1465186216, -5600)
p2 = Vector(699017.5566976141, 2103561.5604983107, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(699617.9166155375, 2102187.1465186216, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_69')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(704648.7836114571, 2101121.1489664526, -5600)
p2 = Vector(705531.3556554959, 2101810.689818818, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(704448.7836114571, 2100771.1489664526, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_70')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(705725.4089183855, 2101708.497200877, -5600)
p2 = Vector(704700.9949386953, 2100908.137282951, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(705525.4089183855, 2101358.497200877, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_71')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(945534.155693622, 2128774.732272191, -5600)
p2 = Vector(946515.4002581228, 2128137.504601231, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(945334.155693622, 2128424.732272191, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_72')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(945425.2278866189, 2128606.998158603, -5600)
p2 = Vector(946406.4724511189, 2127969.770487642, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(945225.2278866189, 2128256.998158603, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_73')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(944918.8258613279, 2126551.132893376, -5600)
p2 = Vector(945757.4964292779, 2126006.4938583653, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(944718.8258613279, 2126201.132893376, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_74')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(945866.4242362789, 2126174.227971955, -5600)
p2 = Vector(945027.753668334, 2126718.867006963, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(945666.4242362789, 2125824.227971955, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_75')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(948405.075113396, 2129569.305544582, -5600)
p2 = Vector(949344.386149499, 2128959.309825373, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(948205.075113396, 2129219.305544582, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_76')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(949528.794307616, 2129078.0264258115, -5600)
p2 = Vector(948438.522569284, 2129786.057171326, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(949328.794307616, 2128728.0264258115, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_77')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(948751.5641064668, 2123024.7693467094, -5600)
p2 = Vector(949361.5589864989, 2123964.0790905943, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(948551.5641064668, 2122674.7693467094, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_78')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(949578.3106132409, 2123930.6316347076, -5600)
p2 = Vector(948870.27986773, 2122840.359896372, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(949378.3106132409, 2123580.6316347076, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_79')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(979896.235897116, 2124814.66525817, -5600)
p2 = Vector(979896.235897116, 2123694.66525817, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(979696.235897116, 2124464.66525817, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_80')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(979696.2358971179, 2124814.665258171, -5600)
p2 = Vector(979696.235897116, 2123694.665258169, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(979496.2358971179, 2124464.665258171, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_81')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(917953.167834048, 2144904.4501886833, -5600)
p2 = Vector(917953.167834046, 2143784.4501886833, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(917753.167834048, 2144554.4501886833, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_82')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(917753.167834048, 2144904.450188685, -5600)
p2 = Vector(917753.1678340469, 2143784.4501886843, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(917553.167834048, 2144554.450188685, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_83')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(926633.302946885, 2115628.729940666, -5600)
p2 = Vector(926633.3029468829, 2114458.729940666, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(926433.302946885, 2115278.729940666, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_84')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(926433.3029468829, 2115628.729940666, -5600)
p2 = Vector(926433.3029468829, 2114458.729940666, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(926233.3029468829, 2115278.729940666, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_85')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(979896.235897116, 2098006.8818080937, -5600)
p2 = Vector(979896.235897116, 2096886.881808094, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(979696.235897116, 2097656.8818080937, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_86')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(979696.235897116, 2098006.8818080956, -5600)
p2 = Vector(979696.235897116, 2096886.881808094, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(979496.235897116, 2097656.8818080956, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_87')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(958384.7313473119, 2099862.921237587, -5600)
p2 = Vector(957360.3173676239, 2099062.561319663, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(958184.7313473119, 2099512.921237587, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_88')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(957308.1060403829, 2099275.5730031636, -5600)
p2 = Vector(958190.678084422, 2099965.1138555286, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(957108.1060403829, 2098925.5730031636, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_89')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(952579.431662405, 2100885.6238182224, -5600)
p2 = Vector(951889.89081004, 2101768.1958622616, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(952379.431662405, 2100535.6238182224, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_90')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(951676.8791265389, 2101715.984535021, -5600)
p2 = Vector(952477.239044465, 2100691.570555334, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(951476.8791265389, 2101365.984535021, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_91')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(957328.9693560068, 2102375.5874744635, -5600)
p2 = Vector(958250.9419377089, 2103095.9114005286, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(957128.9693560068, 2102025.5874744635, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_92')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(958374.074232771, 2102938.30924981, -5600)
p2 = Vector(957452.1016510959, 2102217.985323712, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(958174.074232771, 2102588.30924981, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_93')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(955683.9407597109, 2103628.386707126, -5600)
p2 = Vector(956471.9515133168, 2104244.048182452, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(955483.9407597109, 2103278.386707126, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_94')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(955807.0730547389, 2103470.784556374, -5600)
p2 = Vector(956595.0838084059, 2104086.446031701, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(955607.0730547389, 2103120.784556374, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_95')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(165952.81922913768, 2114274.305951071, -5600)
p2 = Vector(165952.81922913768, 2113154.305951071, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(165752.81922913768, 2113924.305951071, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_96')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(165702.8192291386, 2113154.30595107, -5600)
p2 = Vector(165702.81922913832, 2114274.30595107, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(165502.8192291386, 2112804.30595107, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_97')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(169972.8192291368, 2117474.2947449703, -5600)
p2 = Vector(169972.8192291365, 2116304.305951068, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(169772.8192291368, 2117124.2947449703, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_98')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(169772.8192291367, 2117474.2947449703, -5600)
p2 = Vector(169772.8192291367, 2116304.305951068, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(169572.8192291367, 2117124.2947449703, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_99')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(171772.81922913832, 2119259.2930824794, -5600)
p2 = Vector(171772.8192291425, 2118119.2930824794, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(171572.81922913832, 2118909.2930824794, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_100')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(171972.81922914082, 2119259.2930824794, -5600)
p2 = Vector(171972.81922914082, 2118119.2930824794, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(171772.81922914082, 2118909.2930824794, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_101')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(171772.82795472082, 2114374.2930824766, -5600)
p2 = Vector(173092.8279547214, 2114374.2930824775, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(171572.82795472082, 2114024.2930824766, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_102')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(171772.82795472082, 2114124.2930824757, -5600)
p2 = Vector(173092.8279547214, 2114124.2931295773, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(171572.82795472082, 2113774.2930824757, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_103')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(188199.64721912262, 2128434.8258334054, -5600)
p2 = Vector(189155.731666587, 2127813.937333498, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(187999.64721912262, 2128084.8258334054, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_104')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(189264.65947358578, 2127981.6714470843, -5600)
p2 = Vector(188308.5750261253, 2128602.559946997, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(189064.65947358578, 2127631.6714470843, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_105')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(188764.75618416647, 2130452.5663661873, -5600)
p2 = Vector(189745.9887333471, 2129815.3464980675, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(188564.75618416647, 2130102.5663661873, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_106')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(188873.68399116822, 2130620.3004797753, -5600)
p2 = Vector(189854.9165403485, 2129983.0806116583, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(188673.68399116822, 2130270.3004797753, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_107')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(191744.5913956067, 2131414.8815551028, -5600)
p2 = Vector(192683.90243170538, 2130804.885835885, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(191544.5913956067, 2131064.8815551028, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_108')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(192820.06219045952, 2131014.553477872, -5600)
p2 = Vector(191880.75115436083, 2131624.549197088, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(192620.06219045952, 2130664.553477872, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_109')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(192923.2751566018, 2125784.5972315585, -5600)
p2 = Vector(192204.3497596105, 2124677.549201115, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(192723.2751566018, 2125434.5972315585, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_110')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(192713.6075146129, 2125920.756990309, -5600)
p2 = Vector(191994.6821176228, 2124813.7089598663, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(192513.6075146129, 2125570.756990309, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_111')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(195822.9119414831, 2102529.266458191, -5600)
p2 = Vector(195010.2387940536, 2103569.4406529525, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(195622.9119414831, 2102179.266458191, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_112')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(196019.914629885, 2102683.1818270227, -5600)
p2 = Vector(195207.24148245552, 2103723.3560217833, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(195819.914629885, 2102333.1818270227, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_113')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(200647.6223226458, 2101121.1490135565, -5600)
p2 = Vector(201530.1943666868, 2101810.6898659226, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(200447.6223226458, 2100771.1490135565, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_114')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(201684.1184521272, 2101613.6760207666, -5600)
p2 = Vector(200801.5464080851, 2100924.1351684043, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(201484.1184521272, 2101263.6760207666, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_115')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(201590.45739507937, 2104941.4867664715, -5600)
p2 = Vector(200668.4856382836, 2104221.163484835, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(201390.45739507937, 2104591.4867664715, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_116')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(201713.58969014458, 2104783.8846157454, -5600)
p2 = Vector(200791.6179333488, 2104063.5613341136, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(201513.58969014458, 2104433.8846157454, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_117')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(198968.29546431458, 2105430.8657697244, -5600)
p2 = Vector(199866.62772342318, 2106132.719851599, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(198768.29546431458, 2105080.8657697244, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_118')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(199091.4277593799, 2105273.263619003, -5600)
p2 = Vector(199989.76001848868, 2105975.1177008776, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(198891.4277593799, 2104923.263619003, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_119')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285263.98051795695, 2113434.3059039568, -5600)
p2 = Vector(283063.98051795695, 2113434.3059039554, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285063.98051795695, 2113084.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_120')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(284763.98578671494, 2118004.3059049165, -5600)
p2 = Vector(284763.98491015786, 2116993.9110234524, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(284563.98578671494, 2117654.3059049165, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_121')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(284763.98404642707, 2116293.9110234524, -5600)
p2 = Vector(284763.98051795695, 2113434.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(284563.98404642707, 2115943.9110234524, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_122')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(283063.98051795695, 2113434.3059039554, -5600)
p2 = Vector(283063.98051795765, 2108393.9110234575, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(282863.98051795695, 2113084.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_123')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(283063.98051795777, 2107693.9110234603, -5600)
p2 = Vector(283063.9805179579, 2107034.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(282863.98051795777, 2107343.9110234603, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_124')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(283063.9805179579, 2107034.3059039568, -5600)
p2 = Vector(285033.98051795736, 2107034.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(282863.9805179579, 2106684.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_125')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285033.98051795736, 2107534.3059039568, -5600)
p2 = Vector(285033.98051795695, 2105634.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(284833.98051795736, 2107184.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_126')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285033.98051795695, 2105634.3059039568, -5600)
p2 = Vector(289583.98689722974, 2105634.3059039554, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(284833.98051795695, 2105284.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_127')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285533.98051795695, 2106134.3059039568, -5600)
p2 = Vector(289583.98689722974, 2106134.3059039554, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285333.98051795695, 2105784.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_128')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285533.98051795736, 2107534.3059039568, -5600)
p2 = Vector(285533.98051795695, 2105634.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285333.98051795736, 2107184.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_129')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(283563.9805179579, 2107534.3059039568, -5600)
p2 = Vector(285533.98051795736, 2107534.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(283363.9805179579, 2107184.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_130')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(283563.98051795695, 2112934.3059039568, -5600)
p2 = Vector(283563.98051795777, 2108393.9110234575, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(283363.98051795695, 2112584.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_131')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285263.97990100645, 2112934.3059039568, -5600)
p2 = Vector(283063.9805179579, 2112934.3059039554, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285063.97990100645, 2112584.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_132')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285263.98578671494, 2118004.3059049165, -5600)
p2 = Vector(285263.98491015786, 2116993.9110234524, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285063.98578671494, 2117654.3059049165, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_133')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285263.98404642707, 2116293.9110234524, -5600)
p2 = Vector(285263.97990100645, 2112934.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285063.98404642707, 2115943.9110234524, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_134')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(293172.82795472257, 2121114.2930825227, -5600)
p2 = Vector(295772.82795472164, 2121114.2930825227, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(292972.82795472257, 2120764.2930825227, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_135')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(295773.98051795695, 2119914.3059039544, -5600)
p2 = Vector(295772.82795472164, 2121114.2930825227, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(295573.98051795695, 2119564.3059039544, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_136')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(295773.98051795695, 2119914.3059039544, -5600)
p2 = Vector(300273.9805179607, 2119914.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(295573.98051795695, 2119564.3059039544, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_137')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(300273.9805179607, 2119914.3059039568, -5600)
p2 = Vector(300273.98051797086, 2115784.3059039484, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(300073.9805179607, 2119564.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_138')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302003.98051795695, 2116284.3059039526, -5600)
p2 = Vector(300773.98051796947, 2116284.3059039493, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(301803.98051795695, 2115934.3059039526, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_139')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(291213.99824930384, 2119504.3058568616, -5600)
p2 = Vector(292673.98051795695, 2119504.3058568607, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(291013.99824930384, 2119154.3058568616, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_140')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(293173.9805179564, 2119004.3058568607, -5600)
p2 = Vector(293172.82795472257, 2121114.2930825227, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(292973.9805179564, 2118654.3058568607, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_141')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(291213.99824930384, 2119004.3058568616, -5600)
p2 = Vector(293173.9805179564, 2119004.3058568607, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(291013.99824930384, 2118654.3058568616, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_142')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(292673.98051795695, 2119504.3058568607, -5600)
p2 = Vector(292672.82795472303, 2121614.2930825227, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(292473.98051795695, 2119154.3058568607, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_143')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(292672.82795472303, 2121614.2930825227, -5600)
p2 = Vector(296272.82795472164, 2121614.2930825227, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(292472.82795472303, 2121264.2930825227, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_144')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(296273.98051795695, 2120414.3059039554, -5600)
p2 = Vector(296272.82795472164, 2121614.2930825227, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(296073.98051795695, 2120064.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_145')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(296273.98051795695, 2120414.3059039554, -5600)
p2 = Vector(298985.13234143285, 2120414.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(296073.98051795695, 2120064.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_146')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(299385.1323414412, 2120414.3059039568, -5600)
p2 = Vector(300773.9805179593, 2120414.3059039577, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(299185.1323414412, 2120064.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_147')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(300773.9805179593, 2120414.3059039577, -5600)
p2 = Vector(300773.98051797086, 2115784.3059039493, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(300573.9805179593, 2120064.3059039577, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_148')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302503.98051795695, 2115784.3059039535, -5600)
p2 = Vector(300273.98051797086, 2115784.3059039484, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(302303.98051795695, 2115434.3059039535, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_149')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302003.98051795695, 2115784.3059039526, -5600)
p2 = Vector(302003.98051795695, 2116984.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(301803.98051795695, 2115434.3059039526, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_150')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302003.98051795695, 2116984.3059039568, -5600)
p2 = Vector(302978.9741386928, 2116984.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(301803.98051795695, 2116634.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_151')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(310329.90311344486, 2116984.3059039693, -5600)
p2 = Vector(312672.64604690677, 2120591.8136664825, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(310129.90311344486, 2116634.3059039693, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_152')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(313109.16229569184, 2121262.227759992, -5600)
p2 = Vector(315184.24207494245, 2124457.5704092425, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(312909.16229569184, 2120912.227759992, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_153')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(315875.09205012635, 2124605.1088360217, -5600)
p2 = Vector(312398.80254598946, 2126862.6376361228, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(315675.09205012635, 2124255.1088360217, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_154')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(312398.80254598946, 2126862.6376361228, -5600)
p2 = Vector(314849.67314765794, 2130636.6474065348, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(312198.80254598946, 2126512.6376361228, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_155')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(314849.67314765794, 2130636.6474065348, -5600)
p2 = Vector(313675.53435252886, 2131399.1420555487, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(314649.67314765794, 2130286.6474065348, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_156')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(313675.53435252886, 2131399.1420555487, -5600)
p2 = Vector(316268.01615919964, 2135391.2139589656, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(313475.53435252886, 2131049.1420555487, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_157')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(317844.71682691766, 2134367.2925731693, -5600)
p2 = Vector(316268.01615919964, 2135391.2139589656, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(317644.71682691766, 2134017.2925731693, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_158')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(317697.7010604474, 2135058.9473746475, -5600)
p2 = Vector(319549.47377952945, 2137910.4273057533, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(317497.7010604474, 2134708.9473746475, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_159')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(309053.98051795876, 2106984.3059039554, -5600)
p2 = Vector(310373.98051834246, 2106984.3059039554, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(308853.98051795876, 2106634.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_160')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302503.98051795695, 2115784.3059039535, -5600)
p2 = Vector(302503.98051795695, 2116484.3059039568, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(302303.98051795695, 2115434.3059039535, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_161')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(315602.77253262134, 2124185.7735520457, -5600)
p2 = Vector(311707.1477445104, 2126715.6218696516, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(315402.77253262134, 2123835.7735520457, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_162')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(311707.1477445104, 2126715.6218696516, -5600)
p2 = Vector(314158.01834617887, 2130489.6316400655, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(311507.1477445104, 2126365.6218696516, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_163')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(314158.01834617887, 2130489.6316400655, -5600)
p2 = Vector(312983.8795510465, 2131252.1262890804, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(313958.01834617887, 2130139.6316400655, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_164')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(312983.8795510465, 2131252.1262890804, -5600)
p2 = Vector(316121.00039273174, 2136082.8687604424, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(312783.8795510465, 2130902.1262890804, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_165')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(317697.7010604474, 2135058.9473746475, -5600)
p2 = Vector(316121.00039273174, 2136082.8687604424, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(317497.7010604474, 2134708.9473746475, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_166')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(317844.71682691766, 2134367.2925731693, -5600)
p2 = Vector(319968.80906350265, 2137638.1077882466, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(317644.71682691766, 2134017.2925731693, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_167')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(309053.98051795876, 2107484.3059039554, -5600)
p2 = Vector(310617.84681262454, 2107484.3059039554, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(308853.98051795876, 2107134.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_168')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(310373.98051834246, 2106984.3059039554, -5600)
p2 = Vector(314646.6711569881, 2101515.5112741063, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(310173.98051834246, 2106634.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_169')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(318423.7551185585, 2096681.0659752036, -5600)
p2 = Vector(322853.43862306885, 2091011.3279285184, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(318223.7551185585, 2096331.0659752036, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_170')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(322853.43862306885, 2091011.3279285184, -5600)
p2 = Vector(323893.6128178235, 2091824.0010759407, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(322653.43862306885, 2090661.3279285184, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_171')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(323893.6128178235, 2091824.0010759407, -5600)
p2 = Vector(324663.18966198666, 2090838.9876339366, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(323693.6128178235, 2091474.0010759407, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_172')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(310617.84681262454, 2107484.3059039554, -5600)
p2 = Vector(315040.67653379036, 2101823.3420117716, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(310417.84681262454, 2107134.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_173')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(318817.7596648675, 2096988.8960640137, -5600)
p2 = Vector(322939.6132622096, 2091713.1640429837, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(318617.7596648675, 2096638.8960640137, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_174')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(322545.6078854055, 2091405.3333053207, -5600)
p2 = Vector(323979.7874569623, 2092525.8371904045, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(322345.6078854055, 2091055.3333053207, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_175')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(323979.7874569623, 2092525.8371904045, -5600)
p2 = Vector(325057.19503878994, 2091146.8183715995, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(323779.7874569623, 2092175.8371904045, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_176')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(310373.98051834246, 2106984.3059039554, -5600)
p2 = Vector(310767.98589514475, 2107292.1366416197, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(310173.98051834246, 2106634.3059039554, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_177')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(325892.48643760855, 2091799.4195354404, -5600)
p2 = Vector(324663.18966198666, 2090838.9876339366, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(325692.48643760855, 2091449.4195354404, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_178')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(325584.6556999456, 2092193.4249122445, -5600)
p2 = Vector(326452.73838015436, 2091082.3297496587, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(325384.6556999456, 2091843.4249122445, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_179')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(325978.66107674927, 2092501.2556499075, -5600)
p2 = Vector(326846.74375695805, 2091390.1604873217, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(325778.66107674927, 2092151.2556499075, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_180')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(325978.66107674927, 2092501.2556499075, -5600)
p2 = Vector(324749.36430112465, 2091540.8237484004, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(325778.66107674927, 2092151.2556499075, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_181')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(310601.380963258, 2116484.3059039568, -5600)
p2 = Vector(315875.09205012646, 2124605.1088360217, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(310401.380963258, 2116134.3059039568, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_182')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285363.98689722974, 2119504.3059049165, -5600)
p2 = Vector(290613.98689722596, 2119504.3059049165, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285163.98689722974, 2119154.3059049165, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_183')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(285363.99824930757, 2118004.3059544964, -5600)
p2 = Vector(290613.99824930384, 2118004.3059544964, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(285163.99824930757, 2117654.3059544964, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_184')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(290183.98051795736, 2105634.3059520144, -5600)
p2 = Vector(295272.83436623635, 2105634.3059520144, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(289983.98051795736, 2105284.3059520144, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_185')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(303578.98051795695, 2116984.3059520144, -5600)
p2 = Vector(309673.98051797086, 2116984.3059520153, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(303378.98051795695, 2116634.3059520144, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_186')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(295872.83436623635, 2106984.3059049156, -5600)
p2 = Vector(301703.98689722735, 2106984.3059049165, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(295672.83436623635, 2106634.3059049156, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_187')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302303.98689722316, 2106984.3059049165, -5600)
p2 = Vector(308253.98689722316, 2106984.3059049165, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(302103.98689722316, 2106634.3059049165, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_188')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(303578.98051795695, 2115884.3059520144, -5600)
p2 = Vector(309673.98051797086, 2115884.3059520153, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(303378.98051795695, 2115534.3059520144, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_189')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(315016.06804170134, 2101042.7048705756, -5600)
p2 = Vector(317931.22510780214, 2097311.4756410774, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(314816.06804170134, 2100692.7048705756, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_190')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(290183.98051795736, 2106834.3059520144, -5600)
p2 = Vector(295272.83436623635, 2106834.3059520144, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(289983.98051795736, 2106484.3059520144, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_191')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(295872.83436623635, 2107984.3059049156, -5600)
p2 = Vector(301703.98689722724, 2107984.3059049165, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(295672.83436623635, 2107634.3059049156, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_192')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(302303.98689722316, 2107984.3059049165, -5600)
p2 = Vector(308253.98689722316, 2107984.3059049165, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(302103.98689722316, 2107634.3059049165, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_193')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(316119.28309675085, 2101904.6309360317, -5600)
p2 = Vector(319034.44018616807, 2098173.4000129034, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(315919.28309675085, 2101554.6309360317, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_194')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(159362.82560840904, 2119504.305903971, -5600)
p2 = Vector(164612.82560840526, 2119504.305903971, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(159162.82560840904, 2119154.305903971, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_195')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(159362.82560840904, 2119004.305903971, -5600)
p2 = Vector(164612.82560840526, 2119004.305903971, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(159162.82560840904, 2118654.305903971, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_196')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(159262.81922913625, 2113434.30595107, -5600)
p2 = Vector(157062.81922913625, 2113434.305951069, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(159062.81922913625, 2113084.30595107, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_197')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(158762.82449789424, 2118004.305904285, -5600)
p2 = Vector(158762.82362133716, 2116993.911070576, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(158562.82449789424, 2117654.305904285, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_198')
obj.Shape = beam
beam_rc_g.addObject(obj)

p1 = Vector(158762.82275760634, 2116293.911070576, -5600)
p2 = Vector(158762.81922913625, 2113434.30595107, -5600)
d = p2.sub(p1)
length = d.Length
angle = d.getAngle(Vector(1,0,0))
beam = Part.makeBox(400.0, 700.0, length, Vector(158562.82275760634, 2115943.911070576, -5600))
obj = doc.addObject('Part::Feature', 'B_RC_199')
obj.Shape = beam
beam_rc_g.addObject(obj)

# SLABS: 5
slab_g = doc.addObject('App::DocumentObjectGroup', 'Slabs')

wire = Part.makePolygon([Vector(225110, 2155099, -5600), Vector(234497, 2155099, -5600), Vector(234497, 2140902, -5600), Vector(225110, 2140902, -5600)])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, 210))
obj = doc.addObject('Part::Feature', 'Slab_0')
obj.Shape = slab
slab_g.addObject(obj)

wire = Part.makePolygon([Vector(225110, 2153796, -5600), Vector(234497, 2153796, -5600), Vector(234497, 2140902, -5600), Vector(225110, 2140902, -5600)])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, 210))
obj = doc.addObject('Part::Feature', 'Slab_1')
obj.Shape = slab
slab_g.addObject(obj)

wire = Part.makePolygon([Vector(99110, 2155099, -5600), Vector(108497, 2155099, -5600), Vector(108497, 2140902, -5600), Vector(99110, 2140902, -5600)])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, 210))
obj = doc.addObject('Part::Feature', 'Slab_2')
obj.Shape = slab
slab_g.addObject(obj)

wire = Part.makePolygon([Vector(99110, 2153796, -5600), Vector(108497, 2153796, -5600), Vector(108497, 2140902, -5600), Vector(99110, 2140902, -5600)])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, 210))
obj = doc.addObject('Part::Feature', 'Slab_3')
obj.Shape = slab
slab_g.addObject(obj)

wire = Part.makePolygon([Vector(729110, 2155099, -5600), Vector(738497, 2155099, -5600), Vector(738497, 2140902, -5600), Vector(729110, 2140902, -5600)])
face = Part.Face(wire)
slab = face.extrude(Vector(0, 0, 210))
obj = doc.addObject('Part::Feature', 'Slab_4')
obj.Shape = slab
slab_g.addObject(obj)

doc.recompute()
print('Model 101동 ready')