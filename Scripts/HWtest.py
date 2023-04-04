import math

import serial
import subprocess
import json
import datetime
import time
import os.path

# This script uses subprocess to read and write to PMBus to change voltages on the FPGA.
# After which serial port is read to check results from the LDPC running on the board.

# PMBus read example: ( get the actual V on VCCINT )
# FusionParamReader --address 52 --rail 1 READ_VOUT --cols decoded --no-header
# PMBus write example: ( Set V on VCCBRAM to 0.817 volts )
# FusionParamWriter --address 53 --rail 4 --cmd-id VOUT_COMMAND --value-decoded  0.817
# More info with commands FusionParamReader --helps and FusionParamWriter --help

# init serial
ser = serial.Serial(port="COM3", baudrate=115200, timeout=1)

# script config. TODO: allow changing these with cmd arguments.
do_v_change = True
read_rails = True
do_write = True
record_default = True
print_output_table = True

v_value = 1  # "Normalized" start value for the voltage.
interesting_range = [0.735, 0.710]  # the range where v_value lowers by the precise value.

v_change_max = 0.05  # Change of v_value outside the interesting range.
v_change_precise = 0.001  # Change of v_value inside the interesting range.

runs_in_set = 30  # amount of datapoints for each v_value.


# Values for each rail:
rails = [  # If rail is selected, its status will be read and writen to. scale is applied to v_value on writes.
    {"selected": True, "address": "52", "rail": "1", "name": "VCCINT", "defaultV": 1.0, "change-scale": 1},
    {"selected": False, "address": "52", "rail": "2", "name": "VCCPINT", "defaultV": 1.0, "change-scale": 1},
    {"selected": False, "address": "52", "rail": "3", "name": "VCCAUX", "defaultV": 1.8, "change-scale": 1},
    {"selected": False, "address": "52", "rail": "4", "name": "VCCPAUX", "defaultV": 1.8, "change-scale": 1},
    {"selected": False, "address": "53", "rail": "1", "name": "VCCADJ", "defaultV": 2.5, "change-scale": 1},
    {"selected": False, "address": "53", "rail": "2", "name": "VCC1V5PS", "defaultV": 1.5, "change-scale": 1},
    {"selected": False, "address": "53", "rail": "3", "name": "VCC_MIO", "defaultV": 1.8, "change-scale": 1},
    {"selected": True, "address": "53", "rail": "4", "name": "VCCBRAM", "defaultV": 1.0, "change-scale": 0.86},
    {"selected": False, "address": "54", "rail": "1", "name": "VCC3V3", "defaultV": 3.3, "change-scale": 1},
    {"selected": False, "address": "54", "rail": "2", "name": "VCC2V5", "defaultV": 2.5, "change-scale": 1},
]

# Commands to run when voltage is changed. value multiplier is used so the upper and lower boundaries are correct.
power_commands = [
    {"cmd-id": "POWER_GOOD_OFF", "value-multiplier": 1 - 0.15},
    {"cmd-id": "POWER_GOOD_ON", "value-multiplier": 1 - 0.10},
    {"cmd-id": "VOUT_UV_FAULT_LIMIT", "value-multiplier": 1 - 0.15},
    {"cmd-id": "VOUT_UV_WARN_LIMIT", "value-multiplier": 1 - 0.10},
    {"cmd-id": "VOUT_MARGIN_LOW", "value-multiplier": 1 - 0.05},
    {"cmd-id": "VOUT_COMMAND", "value-multiplier": 1},  # This is the actual command to change the voltage.
    {"cmd-id": "VOUT_MARGIN_HIGH", "value-multiplier": 1 + 0.05},
    {"cmd-id": "VOUT_OV_WARN_LIMIT", "value-multiplier": 1 + 0.10},
    {"cmd-id": "VOUT_OV_FAULT_LIMIT", "value-multiplier": 1 + 0.15}
]

# Globals
set_count = 0
lastsave = ""
powerstatus = {}
testcases = []

start_time = 0
set_param_time = 0
loop_time = 0
estimate_time_left = "N/A"

hw_conf = {
    "max_iter": 15,
    "endsame": 3,
    "blocksize": 1024,
    "paritychecks": 6,
    "cnodes": 384,
    "msglen": 613,
    "crc": 32,
}  # will be read from serial on start of the script.


def main():
    global start_time
    calculate_set_count()
    got_pow_status = True
    got_ser_out = True
    str_date_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "ldpc_power_log_" + str_date_time + ".data"
    i = 0
    loop = 0
    times = {"start": 0, "set": 0, "get": 0, "read": 0}
    ret = reset_board_voltages()
    if not ret:
        print("ERROR RESETING THE VOLTAGE RAILS.")
        return
    start_time = time.time()
    if record_default:
        record_default_values()
    get_default_cases()
    print("Starting data gathering..")

    # Main loop
    while True:
        times["start"] = time.time()
        if do_v_change and loop > 0:  # Just don't do this on first loop...
            i += 1
            if i % runs_in_set == 0:
                ret = set_next_v_value()
                if ret != 0:
                    break
        times["set"] = time.time()
        if read_rails:
            pow_status = read_power_status()
        else:
            time.sleep(1)  # Simulate time passing if rails are not actually read...
            pow_status = True
        times["get"] = time.time()
        ser_out = read_serial()
        times["read"] = time.time()
        if pow_status and ser_out:
            datapoint = {
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "power": pow_status,
                "results": ser_out
            }
            if do_write:
                write_data(datapoint, filename)
            save_results(datapoint)
            if print_output_table:
                print_results(times, loop)
        got_pow_status, got_ser_out = check_status(bool(pow_status), bool(ser_out), got_pow_status, got_ser_out)
        if pow_status and ser_out:
            set_time_estimates(times, loop)
        loop += 1
        # The loop never ends if do_v_change is false. Might want to add ending clause here.

    print("Tests done")


def check_status(pows, sero, got_pow, got_ser):
    # Just a simple and ugly func to print status when reading power or serial fails or restarts..
    if not pows and got_pow:
        print("Couldn't read Power status")
        got_pow = False
    if pows and not got_pow:
        got_pow = True
        if got_pow and got_ser:
            print("Reads ok!")
    if not sero and got_ser:
        print("Couldn't read Serial output")
        got_ser = False
    if sero and not got_ser:
        got_ser = True
        if got_pow and got_ser:
            print("Reads ok!")
    return got_pow, got_ser


def read_power_status():
    # Loops trough selected power rails and returns their values.
    output = {}
    for rail in rails:
        if rail["selected"]:
            output[rail["name"]] = read_rail_power_status(rail)
            if not output[rail["name"]]:
                return False
    return output


def read_rail_power_status(rail):
    # Calls FusionParamReader with correct params to get info from rail.
    result = subprocess.run(["FusionParamReader", "--address", rail["address"], "--rail", rail["rail"], "VOUT_COMMAND", "READ_VOUT", "READ_IOUT", "READ_POUT", "READ_TEMPERATURE_1", "READ_TEMPERATURE_2", "--cols", "DecodedNumeric", "--no-header", "--format", "tab"], stdout=subprocess.PIPE)
    out = result.stdout.decode('utf-8').split("\n")
    if len(out) == 7:  # the split results in 1 extra value at the end so + 1...
        output = { # Parse data from command output.
            "VOUT_COMMAND": float(out[0].strip().replace(",", ".")),
            "READ_VOUT": float(out[1].strip().replace(",", ".")),
            "READ_IOUT": float(out[2].strip().replace(",", ".")),
            "READ_POUT": float(out[3].strip().replace(",", ".")),
            "READ_TEMPERATURE_1": float(out[4].strip().replace(",", ".")),
            "READ_TEMPERATURE_2": float(out[5].strip().replace(",", "."))
        }
        return output
    print(out)
    return False


def read_serial():
    # Reads the latest full run cycle from serial and returns them.
    ser.flushInput()  # Clear serial input
    output = []
    read_status = 0  # no end found.. wating for next cycle
    while True:
        serialout = ser.readline()
        if serialout:
            values = serialout.decode("utf-8").strip().split(" ")
            if len(values[0]) > 0:
                if values[0][0] == "#":
                    if values[0] == "#RESULT" and read_status == 1:  # Read results only at the start of fresh cycle
                        result = {
                            "Algorithm": values[1],
                            "testcase": int(values[2]),
                            "duration": int(1000000*float(values[5])),
                            "iteration": int(values[6]),
                            "crc_result": int(values[7]),
                            "gold_compare": int(values[8])
                        }
                        output.append(result)

                    if values[0] == "#RUN_DONE":
                        if read_status == 0:   # Cycle ended. start reading results..
                            read_status = 1
                        else:  # Full cycle ended. stop reading..
                            break
        else:
            print("Serial timeout")
            break
    return output


def record_default_values():
    # Runs at the start to get default values and config info from the board.
    # works like read_serial() but saves values as default. these functions could be merged.
    global hw_conf
    global testcases
    ser.flushInput()  # Clear serial input
    output = []
    read_status = 0
    while True:
        serialout = ser.readline()
        if serialout:
            values = serialout.decode("utf-8").strip().split(" ")
            if len(values[0]) > 0:
                if values[0][0] == "#":
                    if values[0] == "#RESULT" and read_status == 1:
                        result = {
                            "Algorithm": values[1],
                            "testcase": int(values[2]),
                            "snr": float(values[3]),
                            "biterror": int(values[4]),
                            "duration": int(1000000*float(values[5])),
                            "iteration": int(values[6]),
                            "crc_result": int(values[7]),
                            "gold_compare": int(values[8])
                        }
                        output.append(result)
                    if values[0] == "#CONFIG":
                        # get run config from the board. (The board shouts these before running each test cycle)
                        hw_conf = {
                            "max_iter": int(values[2]),
                            "endsame": int(values[3]),
                            "blocksize": int(values[4]),
                            "paritychecks": int(values[5]),
                            "cnodes": int(values[6]),
                            "msglen": int(values[7]),
                            "crc": int(values[8])
                        }
                    if values[0] == "#RUN_DONE":
                        if read_status == 0:
                            read_status = 1
                        else:
                            break
        else:
            print("Serial timeout while reading defaults..")

    # Save default values
    tc = []
    testcases = []  # Testcases is a global list that holds current and default values for each testcase.
    for case in output:
        if not case["testcase"] in tc:
            tc.append(case["testcase"])
    for i in range(len(tc)):
        testcases.append({"snr": 0, "error": 0, "defaults": {"SPD": {}, "HDD": {}}, "current": {"SPD": {}, "HDD": {}}})
    for case in output:
        testcases[case["testcase"] - 1]["snr"] = case["snr"]
        testcases[case["testcase"] - 1]["errors"] = case["biterror"]
        testcases[case["testcase"] - 1]["defaults"][case["Algorithm"]] = {
            "duration": case["duration"],
            "iteration": case["iteration"],
            "crc_result": case["crc_result"],
            "gold_compare": case["gold_compare"]
        }
    save_defaults()  # Writes these to testcases.json


def set_next_v_value():
    # Lowers the voltage by v_change_max until it hits the interesting range.
    # When on the interesting range the voltage is lowered by v_change_precise.
    # When lower bounds of the interesting range is hit, 1 is returned and the mainloop ends.
    global v_value  # v_value holds the current normalized target voltage. rails change-scale affects the actual target.
    if v_value > interesting_range[0]:
        v_value -= v_change_max
        if v_value < interesting_range[0]:
            v_value = interesting_range[0]
    elif v_value > interesting_range[1]:
        v_value -= v_change_precise
    else:
        print("REACHED END")
        return 1
    for rail in rails:
        if rail["selected"]:
            write_v_change(rail, v_value)
    return 0


def write_v_change(rail, val, do_scale=True, reverse_order=False):
    # Writes the desired voltage to rail.
    # Calls FusionParamWriter with correct params to write voltage target to the rail.
    c_scale = rail["change-scale"]
    if not do_scale:
        c_scale = 1
    if val * c_scale > rail["defaultV"]:
        # This should never happen. Just a final check to not accidentally fry the board.
        print(f'ERROR TRYING TO WRITE LARGER VOLTAGE THAN DEFAULT ON {rail["name"]}!')
        return
    for i in range(len(power_commands)):
        # Loops through all needed commands to carefully set lower and upper boundaries for voltage.
        # This actually takes a huge chunk of the runtime...
        # Maybe the boundaries could be set to larger values at the start of the script and do less here.
        if not reverse_order:  # When voltage is raised, for example in reset, the commands are reversed...
            p = power_commands[i]
        else:
            p = power_commands[len(power_commands)-1-i]
        com_str = f'FusionParamWriter --address {rail["address"]} --rail {rail["rail"]} --cmd-id {p["cmd-id"]} --value-decoded {rail["defaultV"] * c_scale * val * p["value-multiplier"] :.3f} --quiet'
        subprocess.run(com_str.split(" "))


def write_data(data, filename):
    # Writes results and config data as json lines. The file itself is not json but each line can be parsed on its own.
    if not os.path.isfile(filename):
        # If the file does not exist, it will be created and config will be written to lines 1 and 2.
        def_vals = []
        for case in testcases:
            def_vals.append({
                "snr": case["snr"],
                "errors": case["errors"],
                "results": case["defaults"]
            })
        def_vals_line = json.dumps(def_vals)
        hw_conf_line = json.dumps(hw_conf)
        with open(filename, "w") as file:
            file.write(def_vals_line + "\n")
            file.write(hw_conf_line + "\n")

    # write each datapoint as a line in json format.
    json_line = json.dumps(data)
    with open(filename, "a") as file:
        file.write(json_line + "\n")


def get_default_cases():
    # Reads the default values from file.
    # Not needed anymore since the default values can be checked from the serial each time...
    global testcases
    with open("testcases.json", "r") as file:
        testcases = json.load(file)


def save_results(data):
    # Write the datapoint results to global variables for easier access.
    global lastsave
    global powerstatus
    global testcases
    global record_default
    if read_rails:
        powerstatus = data["power"]
    else:
        powerstatus = {}
    lastsave = data["timestamp"]

    for c in range(len(testcases)):
        testcases[c]["current"]["SPD"]["new"] = False
        testcases[c]["current"]["HDD"]["new"] = False
    for res in data["results"]:
        testcases[res["testcase"]-1]["current"][res["Algorithm"]] = res
        # If the script is not set to get full runs at the same time, "new" flag tells which values are updated on print
        testcases[res["testcase"]-1]["current"][res["Algorithm"]]["new"] = True


def save_defaults():
    # Saves the default values to testcases.json for later access.
    json_line = json.dumps(testcases)
    with open("testcases.json", "w") as file:
        file.write(json_line)


def calculate_set_count():
    # A lazy way to calculate how many sets will it take to run the script. (Uses same logic as the script itself...)
    # Could be done with few divisions instead.
    global set_count
    i = 0
    v_val = v_value
    while True:
        i += 1
        if v_val > interesting_range[0]:
            v_val -= v_change_max
            if v_val < interesting_range[0]:
                v_val = interesting_range[0]
        elif v_val > interesting_range[1]:
            v_val -= v_change_precise
        else:
            break
    set_count = i


def set_time_estimates(t, loop):
    # Calculates the estimated time for the script.
    # Not accurate but still better estimation than what Windows tells you on file transfer.
    global set_param_time
    global loop_time
    global estimate_time_left
    runs_left = set_count*runs_in_set - loop - 2
    spt = t["set"] - t["start"]
    loopt = time.time() - t["start"]
    setnum = int(math.floor(loop/runs_in_set))
    if spt > 0.01:
        set_param_time = (set_param_time * setnum + spt)/(setnum+1)
    loop_time = (loop_time * loop + (loopt-spt))/(loop+1)

    if set_param_time > 0.001 and loop_time > 0.001:
        s_left = runs_left * loop_time + (set_count - setnum - 1) * set_param_time
        estimate_time_left = str(datetime.timedelta(seconds=int(s_left)))


def reset_board_voltages():
    # Check if selected rail voltages are not set to defaults. The voltage is gradually set to the default value.
    # This can take a long time if voltage starts low so most of the time it's just much faster to reset board manually.
    current_pow = read_power_status()
    if current_pow:
        for railname in current_pow.keys():
            r = current_pow[railname]
            current_voltage = r["VOUT_COMMAND"]
            rail = False
            for i in rails:
                if i["name"] == railname:
                    rail = i
                    break
            if not rail:
                print(f'Error: {railname} default value not found!')
                return False
            if v_value * rail["change-scale"] > rail["defaultV"]:
                print(f'Error: v_value set to larger than {railname} default!')
                return False

            if current_voltage < rail["defaultV"]:
                print(f'{railname} set to lower voltage than default. Resetting voltage.')
                if rail["defaultV"] - current_voltage > (v_change_max / rail["change-scale"])*4:
                    print(f'This can take a long time. Resetting the board manually might be faster.')

                while current_voltage < rail["defaultV"]:
                    current_voltage += v_change_max / rail["change-scale"]
                    if current_voltage > rail["defaultV"]:
                        current_voltage = rail["defaultV"]
                    write_v_change(rail, current_voltage, do_scale=False, reverse_order=True)
                print("done.")
            elif current_voltage > rail["defaultV"]:
                print(f'Error: {railname} set to higher voltage than default!')
                return False
        return True
    return False


def print_results(t, loop):
    # Prints the results to the output. depending on the terminal config. This might result in the text flashing.
    lines = []
    lines.append("#############################################################################################################################################")
    lines.append(f'Set V: {t["set"]-t["start"] :8.4f} s     Read V: {t["get"]-t["set"] :8.4f} s     Read results: {t["read"]-t["get"] :8.4f} s   ##  Run time: {str(datetime.timedelta(seconds=int(time.time() - start_time))) :>8}   ETA: {estimate_time_left :>8}   ##  Run: {((loop) % runs_in_set)+1 :2d}/{runs_in_set :2d}    Set: {int(math.floor(loop/runs_in_set))+1 :2d}/{set_count :2d}')
    lines.append("#############################################################################################################################################")
    lines.append("RAIL                   DEFAULT            TARGET             V_OUT              I_OUT              P_OUT             TEMP_1            TEMP_2")
    for rail in powerstatus.keys():
        r = powerstatus[rail]
        default = 0
        for i in rails:
            if i["name"] == rail:
                default = i["defaultV"]
                break
        lines.append(f'{rail :<8}               {default :.3f} V            {r["VOUT_COMMAND"] :.3f} V            {r["READ_VOUT"]:.3f} V            {r["READ_IOUT"]:.3f} A            {r["READ_POUT"]:.3f} W          {r["READ_TEMPERATURE_1"]} °C           {r["READ_TEMPERATURE_2"]} °C')
    lines.append("#############################################################################################################################################")
    lines.append("TESTCASE      ##   Sum Product Decoding                                       ##   Hard Decision Decoding")
    lines.append("CASE  SNR ERR ##    ITERATIONS          DURATION          CRC      ERRORS     ##    ITERATIONS          DURATION         CRC      ERRORS")
    i = 0
    for case in testcases:
        i += 1
        spdline = get_alg_result_print_line(case, "SPD")
        hddline = get_alg_result_print_line(case, "HDD")
        lines.append(f'{i :< 4} {case["snr"] :> 4} {case["errors"] :> 3} ## {spdline} ## {hddline} ')
    print("\n"+"\n".join(lines))


def get_alg_result_print_line(case, alg):
    line = " N/A                                                          "
    if "duration" in case["current"][alg].keys():
        crc = " OK "
        if case["current"][alg]["crc_result"] != 0:
            crc = "FAIL"
        new = " "
        if case["current"][alg]["new"]:
            new = ">"
        dur_diff = case["current"][alg]["duration"] - case["defaults"][alg]["duration"]
        if dur_diff > 0:
            dur_diff = "+" + str(dur_diff)
        iter = case["current"][alg]["iteration"]
        maxed = " "
        if iter == 0:
            iter = hw_conf["max_iter"]
            maxed = "m"
        if iter < 0:
            iter = -iter
            maxed = "M"
        def_iter = case["defaults"][alg]["iteration"]
        if def_iter == 0:
            def_iter = hw_conf["max_iter"]
        if def_iter < 0:
            def_iter = -iter
        iter_diff = iter - def_iter
        if iter_diff > 0:
            iter_diff = "+" + str(iter_diff)
        error_diff = case["current"][alg]["gold_compare"] - case["defaults"][alg]["gold_compare"]
        if error_diff > 0:
            error_diff = "+" + str(error_diff)
        line = f'{new} '
        line += f'{maxed} {iter :>3} ({iter_diff :>4})   '
        line += f'{case["current"][alg]["duration"] :>7} µs ({dur_diff :>8})   '
        line += f'{crc}   {case["current"][alg]["gold_compare"] :>4} ({error_diff:>5})'
    return line


if __name__ == '__main__':
    main()
