import datetime
import time
import math
import random

from pyldpc import make_ldpc, encode, decode, get_message, utils
import numpy as np


block_size = 1024
parity_check_equations = 6 #d_v
bits_in_equation = 16 #d_c

snr_rangex10 = range(10, 120, 2)
d_c_range = range(2, int(block_size/8))

test_per_snr = 100

max_iter = 16

cr_minim = 0.5
values = ["fail", "iter", "itertime", "operationtime", "snr", "d_v", "d_c", "cr", "maxiter", "mxwin", "nonmxfail"]
header = ["Block Error Rate", "Iteration Rate", "Iteration Time (ms)", "Test Duration (ms)", "Signal to Noise Ratio",
          "Parity Check Equations (d_v)", "Bits In Equation (d_c)", "Code Rate", "Max Iterations Reached",
          "Max Iteration Success", "Error Without Reaching Max Iterations"]

tp = {'A': 2.745, 'AE': -13.445, 'B': 1.259, 'BE': 1.498, 'C': -7.148, 'CE': -1.011, 'D': 2.993}
itp = {"A": 250.448, "AE": -3.752}

def sanity_check():
    snr = 15
    H, G = make_ldpc(block_size, parity_check_equations, bits_in_equation, systematic=True, sparse=True, seed=random.randint(0, 10000))
    k = G.shape[1]
    msg = np.random.randint(2, size=k)
    y = encode(G, msg, snr, seed=random.randint(0, 10000))
    sigma = 10 ** (- snr / 20)
    px = 1
    py = signal_power(list(y))
    snr1 = px/(py-px)
    snr2 = 1/(sigma**2)
    print(10*math.log10(snr1))
    print(10*math.log10(snr2))
    return


def signal_power(items):
    power = 0
    for i in items:
        power += i**2
    power = power/len(items)
    return power


def clamp(num, min_value, max_value):
   return max(min(num, max_value), min_value)


def main():
    str_date_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "test_" + str_date_time + ".csv"
    write_line(header, filename)
    write_line(values, filename)
    tests = 0
    timingtotal = 0
    timing = 0
    for d_c in d_c_range:
        if block_size/d_c != block_size//d_c:
            continue
        step = int(max(d_c/16, 1))
        for d_v in range(2, d_c, step):
            cr = 1-d_v/d_c + (d_v-1)/block_size
            if cr < cr_minim:
                continue
            for snrx10 in snr_rangex10:
                snr = snrx10 / 10.0
                tests += 1
                tps = tp["A"]*pow(snr, tp["AE"])+tp["B"]*pow(d_v, tp["BE"])+tp["C"]*pow(d_c, tp["CE"])+tp["D"]
                itps = clamp(itp["A"]*pow(snr, itp["AE"]), 0, 1)
                timingtotal += itps*tps
    start_time = time.time()
    print(f'{str(datetime.datetime.now().strftime("%H:%M:%S")) :<8}> Tests started. Running {tests*test_per_snr} tests. Good luck!')
    test = 0
    for d_c in d_c_range:
        if block_size/d_c != block_size//d_c:
            continue
        step = int(max(d_c/16, 1))
        for d_v in range(2, d_c, step):
            cr = 1-d_v/d_c + (d_v-1)/block_size
            if cr < cr_minim:
                continue
            chunk_time = time.time()
            chunk_timing = 0
            chunk_tests = 0
            for snrx10 in snr_rangex10:
                snr = snrx10 / 10.0
                result = {"fail": 0, "iter": 0, "itertime": 0, "operationtime": 0, "snr": snr, "d_v": d_v, "d_c": d_c, "cr": f'{cr :.3f}', "maxiter": 0, "mxwin": 0, "nonmxfail": 0}
                for i in range(test_per_snr):
                    opertime = time.time()
                    H, G = make_ldpc(block_size, d_v, d_c, systematic=True, sparse=True, seed=random.randint(0, 10000))
                    k = G.shape[1]
                    msg = np.random.randint(2, size=k)

                    received = encode(G, msg, snr)

                    decodetime = time.time()
                    decoded, n_iter = decode(H, received, snr, maxiter=max_iter)

                    result["itertime"] += (time.time() - decodetime)*1000

                    mxwin = False
                    if n_iter == max_iter:
                        result["maxiter"] += 1
                        n_iter -= 1
                        mxwin = True
                    result["iter"] += n_iter+1

                    for x, b in enumerate(msg):
                        if b != decoded[x]:
                            result["fail"] += 1
                            if not mxwin:
                                result["nonmxfail"] += 1
                            mxwin = False
                            break
                    if mxwin:
                        result["mxwin"] += 1

                    result["operationtime"] += (time.time() - opertime)*1000

                result["itertime"] = f'{result["itertime"]/(result["iter"]*test_per_snr) :.3f}'
                result["operationtime"] = f'{result["operationtime"]/test_per_snr :.3f}'
                result["iter"] = f'{result["iter"]/(test_per_snr*max_iter) :.3f}'
                result["fail"] = f'{result["fail"]/test_per_snr :.3f}'
                result["maxiter"] = f'{result["maxiter"]/test_per_snr :.3f}'
                result["mxwin"] = f'{result["mxwin"]/test_per_snr :.3f}'
                result["nonmxfail"] = f'{result["nonmxfail"]/test_per_snr :.3f}'
                save_result(result, filename)
                chunk_tests += 1
                tps = tp["A"]*pow(snr, tp["AE"])+tp["B"]*pow(d_v, tp["BE"])+tp["C"]*pow(d_c, tp["CE"])+tp["D"]
                itps = clamp(itp["A"]*pow(snr, itp["AE"]), 0, 1)
                chunk_timing += itps*tps

            test += chunk_tests
            timing += chunk_timing
            tcomplete = timing/timingtotal
            dur = int(time.time() - start_time)
            chunkdur = int(time.time() - chunk_time)
            complete = test/tests
            print(f'{str(datetime.datetime.now().strftime("%H:%M:%S")) :<8}> Tests {complete * 100 :6.2f}% complete. Work {tcomplete * 100 :6.2f}% done.')
            print(f'          - Run time Total:    {str(datetime.timedelta(seconds=dur)) :>8}, Last chunk: {str(datetime.timedelta(seconds=chunkdur)) :>8}')
            print(f'          - Estimate by Test%: {str(datetime.timedelta(seconds=int((1/complete-complete)*dur))) :>8}')
            print(f'          - Estimate by Work%: {str(datetime.timedelta(seconds=int((1/tcomplete-tcomplete)*dur))) :>8}')

def save_result(r, filename):
    line = []
    for i in values:
        line.append(str(r[i]))
    write_line(line, filename)


def write_line(line, filename):
    line = ",".join(line)
    with open(filename, "a") as file:
        file.write(line + "\n")


if __name__ == '__main__':
    main()
