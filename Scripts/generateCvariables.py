import math

import numpy
from pyldpc import make_ldpc, encode, decode, get_message, utils
import numpy as np
import random

# Script to generate C header files for hardware and testbench.

# Config. TODO: read conf from cmd arguments..
# rng seeds
matrix_seed = 920125
error_seed = 220492
snr_seed = 0

crc_polynom = f'1{0x04C11DB7:0>32b}'
do_crc = True

block_size = 1024
parity_check_equations = 6
bits_in_equation = 16

snr_range = [6, 8]

testcases = 10  # uses this if readmsgfromfile == false
readmsgfromfile = True


hwheader = "hmatrix.h"
swheader = "testcases.h"

datatypes = {
    "matrix": {
        "float": "float",
        "int": "short int"
    },
    "array": {
        "float": "float",
        "int": "int"
    },
    "var": {
        "float": "float",
        "int": "int"
    }
}

doprint = False
dofile = True
autoname = True

# Globals
sizes = []
sizenames = {}
variables = {}

file = ""
hwfile = ""


def main():
    crc_bits = [0]
    if do_crc:
        crc_bits = list(map(int, crc_polynom))


    # Generate H & G matrix using pyLDPC
    H, G = make_ldpc(block_size, parity_check_equations, bits_in_equation, seed=matrix_seed, systematic=True, sparse=True)
    k = G.shape[1]

    # Optimize and save H matrix
    savearr(optimize_hmatrix(H), "h_matrix", -1)

    msg_length = k
    if do_crc:
        msg_length -= len(crc_bits)-1
        print("LDPC Coderate: %.2f, with crc: %.2f" % (k/block_size, msg_length/block_size))
    else:
        print("LDPC Coderate: %.2f" % (k/block_size))

    blocks = get_messages(msg_length)
    es = error_seed

    # set constants
    sizenames["CRCLEN"] = [len(crc_bits),  ["tb"]]
    sizenames["BLOCKSIZE"] = [block_size,  ["tb","hw"]]
    sizenames["PARITYCHECKS"] = [parity_check_equations,  ["tb","hw"]]
    sizenames["CNODES"] = [int(block_size/bits_in_equation)*parity_check_equations, ["tb", "hw"]]
    sizenames["MSGLEN"] = [msg_length, ["tb"]]
    sizenames["TESTCASECOUNT"] = [len(blocks), ["tb"]]

    snr_s = snr_seed
    for i, msg in enumerate(blocks):

        random.seed(snr_s)
        snr_s += 1
        snr = random.randint(snr_range[0]*10, snr_range[1]*10)/10

        savearr(msg, "sent", i)

        if do_crc:
            msg = numpy.concatenate((msg, get_crc(msg, crc_bits)))

        received = encode(G, msg, snr, seed=es)
        es += 1

        # pyLDPC encoder gives us soft values with errors.
        goldref = decode(H, received, snr)

        hardreceived = np.array([], dtype=np.int32)

        for x, b in enumerate(msg):
            if b != goldref[x]:
                print("Even pyldpc fails..")
                break

        for b in received:
            if b < 0:
                hardreceived = np.append(hardreceived, 1)
            else:
                hardreceived = np.append(hardreceived, 0)

        savearr(hardreceived, "receivedhard", i)
        savearr(received, "receivedfloat", i)
        savearr(goldref, "GoldRef", i)

        savevar(snr, "snr", i)

    namesizes()
    printcvars()


def get_messages(blocksize):
    # Generate random binary messages or read data from file.
    global testcases
    if readmsgfromfile:
        b = []
        fullmsg = message_from_file()
        testcases = math.ceil(len(fullmsg)/blocksize)
        for i in range(testcases):
            block = np.array(fullmsg[i*blocksize:(i+1)*blocksize])
            if len(block) < blocksize:
                block = np.pad(block, (0, blocksize-len(block)), 'constant', constant_values=(0,0))
            b.append(block)
        return b
    else:
        b = []
        for x in range(testcases):
            v = np.random.randint(2, size=blocksize)
            b.append(v)
        return b


def message_from_file():
    # Read text from a file and convert to bits.
    f = open("text.txt", "r")
    text = f.read()
    f.close()
    return text_to_b_int_array(text)


def text_to_b_int_array(s):
    # decode text to individual bits.
    bytes = map(bin, bytearray(s, "utf-8"))
    intarray = []
    for byte in bytes:
        str = byte[2:]
        for s in str:
            intarray.append(int(s))
    return intarray


def get_crc(msg, crc):
    # generate and return crc bits
    padded = np.pad(msg, (0, len(crc)-1), 'constant', constant_values=(0, 0))
    while 1 in padded[:len(msg)]:
        cursor = numpy.where(padded == 1)[0][0]
        for i, b in enumerate(crc):
            padded[cursor+i] = numpy.bitwise_xor(b, padded[cursor+i])
    return padded[len(msg):]


def check_crc(msg, crc):
    # check if result was correct.
    # Todo: complete the func...
    cursor = 0
    while cursor < 99:
        cursor = numpy.where(msg == 1)[0]
        if len(cursor) == 0:
            break
        cursor = cursor[0]

        for i, b in enumerate(crc):
            msg[cursor+i] = numpy.bitwise_xor(b, msg[cursor+i])


def savevar(v, varname, case):
    # check variable properties and save them to be writen later.
    t = str(type(v).__name__)
    vtype = ""
    for k in datatypes["var"].keys():
        if k in t:
            if vtype == "":
                vtype = datatypes["var"][k]
            else:
                print("Multiple datatypes found for: " + str(type(v)) + " Will use: " + vtype)
                break

    if case not in variables.keys():
        variables[case] = []
    variables[case].append({"t": vtype, "n": varname, "s": [], "v": str(v)})


def savearr(v, varname, case):
    # check array properties and save them to be writen later.
    vtype = ""
    vsize = []
    if len(v) > 0:
        if type(v) is np.ndarray:
            vsize.append(len(v))
            t = str(type(v[0]).__name__)
            if type(v[0]) is np.ndarray:
                vsize.append(len(v[0]))
                t = str(type(v[0][0]).__name__)
                for k in datatypes["matrix"].keys():
                    if k in t:
                        if vtype == "":
                            vtype = datatypes["matrix"][k]
                        else:
                            print("Multiple datatypes found for: " + str(type(v[0][0])) + " Will use: " + vtype)
                            break
                if vtype == "":
                    print("No datatype found for: " + str(type(v[0][0])))
                    vtype = t
            else:
                for k in datatypes["array"].keys():
                    if k in t:
                        if vtype == "":
                            vtype = datatypes["array"][k]
                        else:
                            print("Multiple datatypes found for: " + str(type(v[0])) + " Will use: " + vtype)
                            break
                if vtype == "":
                    print("No datatype found for: " + str(type(v[0])))
                    vtype = t

    if type(v) is np.ndarray:
        value = "{"
        if type(v[0]) is np.ndarray:
            rows = []
            for row in v:
                r = "{"
                r += ", ".join(map(str, row))
                r += "}"
                rows.append(r)
            value += ", ".join(rows)
        else:
            value += ", ".join(map(str, v))
        value += "}"
    else:
        value = str(v)
    for s in vsize:
        if s not in sizes:
            sizes.append(s)
    if case not in variables.keys():
        variables[case] = []
    variables[case].append({"t": vtype, "n": varname, "s": vsize[:], "v": value})


def namesizes():
    # Sets array sizes some constant names for cleaner code.
    if not autoname:
        print("Found " + str(len(sizes)) + " sizes:")
        sline = ""
        for s in sizes:
            found = False
            for k in sizenames.keys():
                if s == sizenames[k][0]:
                    sline += '"' + k + '": ' + str(s) + " " + str(sizenames[k][1]) + "  "
                    found = True
                    break
            if not found:
                sline += str(s) + "  "
        print(sline)
        rn = input("Rename? [y/N]")
        if rn == "y":
            for s in sizes:
                inp = input(str(s) + ": ")
                if inp != "":
                    mode = input("0: Testbench only, 1: Hardware only _2: BOTH >")
                    if mode == 0:
                        sizenames[inp] = [s, ["tb"]]
                    elif mode == 1:
                        sizenames[inp] = [s, ["hw"]]
                    else:
                        sizenames[inp] = [s, ["tb", "hw"]]
    else:
        print("\n")


def optimize_hmatrix(hm):
    # Optimizes the hmatrix so that only locations of ones are saved.
    ones = numpy.ndarray((0,parity_check_equations), dtype=np.int32)
    for i in range(hm.shape[1]):
        col = numpy.where(hm[:, i] == 1)
        ones = np.append(ones, col, axis=0)
    return ones


def printcvars():
    # Print and write variables to C format
    # HW HEADER:
    if -1 in variables.keys():

        for k in sizenames.keys():
            if "hw" in sizenames[k][1]:
                dowrite("#define " + k + " " + str(sizenames[k][0]), False)

        dowrite("", False)

        for v in variables[-1]:
            line = v["t"] + " " + v["n"]
            for s in v["s"]:
                line += "[" + get_size(s) + "]"
            line += " = " + v["v"] + ";"
            dowrite(line, False)

    # SW HEADER:

    for k in sizenames.keys():
        if "tb" in sizenames[k][1]:
            dowrite("#define " + k + " " + str(sizenames[k][0]))

    dowrite("")

    if do_crc:
        crbitstr = str(list(map(int, crc_polynom))).replace("[","{").replace("]","}")
        if "CRCLEN" in sizenames.keys():
            dowrite("int crc_bits[CRCLEN] = " + crbitstr + ";")
        else:
            dowrite("int crc_bits[" + str(len(crc_polynom)) + "] = " + crbitstr + ";")
        dowrite("")
    else:
        dowrite("int crc_bits[1] = {0}; //For easier testing..")
        dowrite("")

    dowrite("typedef struct Testcase {")
    for v in variables[0]:
        line = "    " + v["t"] + " " + v["n"]
        for s in v["s"]:
            line += "[" + get_size(s) + "]"
        line += ";"
        dowrite(line)
    dowrite("} Testcase;")
    for case in variables.keys():
        if case == -1:
            continue
        dowrite("\nstruct Testcase case_" + str(case+1) + " = {")
        for v in variables[case]:
            dowrite("    " + v["v"]+",")
        dowrite("};")

    dowrite("\nTestcase * cases[TESTCASECOUNT] = {")
    for case in variables.keys():
        if case == -1:
            continue
        dowrite("    &case_" + str(case+1) + ",")
    dowrite("};")

    if dofile:
        write_to_file()


def get_size(s):
    for k in sizenames.keys():
        if s == sizenames[k][0]:
            return k
    return str(s)


def dowrite(s, sw=True):
    # save to global
    global file
    global hwfile
    if doprint:
        print(s)
    if dofile:
        if sw:
            file += s+"\n"
        else:
            hwfile += s+"\n"


def write_to_file():
    # Write to correct files
    if hwfile != "":
        f = open(hwheader, "w")
        f.write(hwfile)
        f.close()
    f = open(swheader, "w")
    f.write(file)
    f.close()


if __name__ == '__main__':
    main()
