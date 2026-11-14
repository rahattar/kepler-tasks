import numpy as np, time, sys
rng = np.random.default_rng(1)
m, k = 200.0, 2.0e5
alpha = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3
w = np.sqrt(k / m); c = 2 * 0.08 * m * w / (w ** alpha * np.sin(alpha * np.pi / 2))
fs = 1000.0; dt = 1 / fs; T = 60.0; N = int(T * fs)
t = np.arange(N) * dt
fr = np.fft.rfftfreq(N, dt)
F = np.fft.irfft(np.fft.rfft(rng.normal(0, 1, N)) * ((fr > 1) & (fr < 40)), N)
F = 400 * F / F.std()
for t0 in (20.0, 41.0):
    F += 6000 * np.exp(-((t - t0) / 0.01) ** 2)
M = 8 * N
om = 2 * np.pi * np.fft.rfftfreq(M, dt)
x_ex = np.fft.irfft(np.fft.rfft(F, M) / (k - m * om ** 2 + c * (1j * om) ** alpha), M)[:N]

def newmark_gl(Lmem=None):
    h = dt; n = N
    g = np.empty(n + 1); g[0] = 1.0
    for j in range(1, n + 1):
        g[j] = g[j - 1] * (1 - (alpha + 1) / j)
    ca = c / h ** alpha
    x = np.zeros(n); v = 0.0; a = 0.0
    K = 4 * m / h ** 2 + ca * g[0] + k
    for i in range(0, n - 1):
        lo = 0 if Lmem is None else max(0, i + 1 - int(Lmem / h))
        hist = ca * np.dot(g[1:i + 2 - lo], x[i::-1][: i + 1 - lo])
        xn = (F[i + 1] + m * (4 / h ** 2) * (x[i] + h * v) + m * a - hist) / K
        an = 4 / h ** 2 * (xn - x[i] - h * v) - a
        v = v + h / 2 * (a + an); a = an; x[i + 1] = xn
    return x

def err(x):
    return np.abs(x - x_ex).max() / np.abs(x_ex).max(), np.std(x - x_ex) / np.std(x_ex)

for L in (1.0, 5.0, None):
    t1 = time.process_time(); x = newmark_gl(L); el = time.process_time() - t1
    e1, e2 = err(x)
    print("alpha %.2f  Newmark + GL, dt 1 ms, memory %-5s: peak error %5.1f%%  rms error %5.1f%%  %.1f s CPU for %d s of record"
          % (alpha, "full" if L is None else "%.0f s" % L, 100 * e1, 100 * e2, el, T))
