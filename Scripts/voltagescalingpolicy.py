import random

nominal_voltage = 1
current_voltage = 1
critical_voltage = 0.5
voltage_target = 1

v_base_change = 0.2

snr_threshold = 0
normal_freq = 100
freq = 100

stats = {
    "signals_received": 0,
    "retransmits": 0,
    "crc_fails": 0,
    "our_faults": 0,
    "avg_voltage": 1.0,
    "critical_voltage": 0.5
}
def main():
    global stats
    for i in range(1000):
        r = random.randint(0,5) # receiving a signal randomly
        if not r:
            incoming_signal = [1.1,0.2,-1.3,0.4,0.5] # some signal
            snr = random.randint(5,30) # random for now

            result = error_correction(incoming_signal, snr) # The actual policy algorithm

            if result is None:
                stats["retransmits"] += 1
                pass # ASK FOR RETRANSMISSION OF THE SIGNAL
            else:
                pass # Send result forward
            stats["signals_received"] += 1

        check_voltage() #check if target is reached so frequency chan be reset to normal
        stats["avg_voltage"] = (stats["avg_voltage"]*(i+1) + current_voltage)/(i+2)
    stats["critical_voltage"] = critical_voltage
    print(stats)


def check_voltage():
    # Simulates slowly changing voltage
    global current_voltage
    v_change_speed = 0.01
    if voltage_target < current_voltage:
        current_voltage -= v_change_speed
    if voltage_target > current_voltage:
        current_voltage += v_change_speed

    if abs(voltage_target-current_voltage) < v_change_speed:
        reset_freq()


def error_correction(signal, snr):
    global stats
    global critical_voltage
    do_scaling = True
    if snr < snr_threshold:
        do_scaling = False
        set_voltage(nominal_voltage)

    result, crc = do_error_correction(signal, snr)
    if do_scaling:
        if crc: # Everything ok!
            decrease_voltage()
            return result
        else: # FAIL
            stats["crc_fails"] += 1
            previous_voltage = current_voltage
            increase_voltage()
            # ^ changes frequency to work faster.
            result, crc = do_error_correction(signal, snr) # Retry
            if crc: # Everything ok!
                # Was our fault but was fixed by changing params
                stats["our_faults"] += 1
                critical_voltage = (critical_voltage+previous_voltage)/2 #Set new critical voltage.
                return result
            else: # FAIL
                # still didn't work so probably wasn't our fault? Might want to do one more loop just to make sure?
                set_voltage(previous_voltage) # Reset voltage to what it was before changes.
                return None
    else:
        # Our thing was not used so just carry on.
        if crc:
            return result
        else:
            stats["crc_fails"] += 1
            return None




def set_voltage(v):
    global voltage_target
    if v > current_voltage:
        lower_freq(1-abs(v-current_voltage)/v) #Maybe scale frequency with the current voltage change?
    voltage_target = v

def decrease_voltage():
    global voltage_target

    v_change = v_base_change * 0.01 #minimal lowering anycase
    if current_voltage > critical_voltage:
        v_change += v_base_change * (abs((critical_voltage-current_voltage))/critical_voltage)
    v = current_voltage - v_change
    voltage_target = v

def increase_voltage():
    global voltage_target
    v = current_voltage + v_base_change
    if v > nominal_voltage:
        v = nominal_voltage

    if v > current_voltage:
        lower_freq(1-abs(v-current_voltage)/v) #Maybe scale frequency with the current voltage change?
    voltage_target = v


def lower_freq(scale=0.5):
    global freq
    #freq = normal_freq*scale  # Maybe the drop could be scaled depending on what was the voltage difference from nominal?
    freq = normal_freq*0.5  # or just have set scale to be sure...

def reset_freq():
    global freq
    freq = normal_freq

def do_error_correction(signal, snr):
    result = do_ldpc(signal, snr)
    crc = do_crc(result)
    return result, crc

def do_ldpc(signal, srn): # Replace with ldpc
    return signal

def do_crc(bits): # Replace with crc
    if random.randint(0,int((current_voltage*20)+(100-freq))):
        return True
    return False


if __name__ == "__main__":
    main()