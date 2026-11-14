"""Build a nitrogen saturation table (the standard's own) from anchor values close to published data."""
import numpy as np
# anchors: T K, p bar abs, rho_l, rho_v kg/m3, h_l kJ/kg, h_fg kJ/kg
A = np.array([
 [ 77.355, 1.01325, 806.08,  4.612, -122.25, 199.18],
 [ 80.0,   1.3687,  793.94,  6.038, -116.97, 195.55],
 [ 85.0,   2.2903,  771.01,  9.824, -106.87, 188.31],
 [ 90.0,   3.6050,  746.51, 15.079,  -96.52, 180.01],
 [ 95.0,   5.4086,  720.15, 22.136,  -85.73, 170.44],
 [100.0,   7.7814,  690.43, 31.475,  -74.27, 159.22],
 [105.0,  10.823,   656.48, 43.852,  -61.81, 145.68],
 [110.0,  14.671,   616.24, 60.693,  -47.73, 128.92],
 [115.0,  19.413,   565.71, 85.016,  -31.22, 106.79],
])
T = np.arange(77.0, 115.01, 0.5)
def fit(col, log=False, deg=4):
    x = 1.0 / A[:, 0] if log else A[:, 0]
    y = np.log(A[:, col]) if log else A[:, col]
    c = np.polyfit(x, y, deg)
    v = np.polyval(c, 1.0 / T if log else T)
    return np.exp(v) if log else v
p = fit(1, log=True); rl = fit(2); rv = fit(3, log=True); hl = fit(4); hfg = fit(5)
if __name__ == "__main__":
    print("T_K,p_bar,rho_l_kg_m3,rho_v_kg_m3,h_l_kJ_kg,h_v_kJ_kg")
    for i in range(len(T)):
        print("%.1f,%.5f,%.2f,%.3f,%.2f,%.2f" % (T[i], p[i], rl[i], rv[i], hl[i], hl[i] + hfg[i]))
