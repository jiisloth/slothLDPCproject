#include <stdio.h>
#include "platform.h"
#include "xil_printf.h"
#include <stdio.h>
#include <xparameters.h>
#include <xharddecisiondecoding.h>
#include <xsumproductdecoding.h>
#include "xtime_l.h"
//#include "sleep.h"


#include "testcases.h"
#include "testbench.h"

#define MAXITER 15
#define ENDSAME 3

#define BOTH -1

int v = 1; //0 = nothing, 1 = Just values, 2 = Human readable
int runsingle = -1; //-1 for all

#define TESTCASES 0 // 0 = all
#define CASEOFFSET 0

int algorithmtorun = SUMPRODUCT;
int algorithm;
int runs = 0; // 0 == endless

XSumproductdecoding doSumproductdecoding;
XSumproductdecoding_Config *doSumproductdecoding_cfg;

XHarddecisiondecoding doHarddecisiondecoding;
XHarddecisiondecoding_Config *doHarddecisiondecoding_cfg;



int main(){
    init_platform();
    int error = 0;
    int run = 0;
    if(v==2){printf("\nStarting..\n");}
    if(v==1){printf("\n");}
    XTime timestamp;
    while(1){
        XTime_GetTime(&timestamp);
        if(v==2){printf("Run #%d at %lld\n", run, timestamp);}
        if(v==1){printf("#CONFIG %d %d %d %d %d %d %d %d\n", run, MAXITER, ENDSAME, BLOCKSIZE, PARITYCHECKS, CNODES, MSGLEN, CRCLEN-1);}
		if (algorithmtorun == SUMPRODUCT || algorithmtorun == BOTH){
			algorithm = SUMPRODUCT;
			error = do_test_run();
			if (error == 2){
				break;
			}
		}
		if (algorithmtorun == HARDDECISION || algorithmtorun == BOTH){
			algorithm = HARDDECISION;
			error = do_test_run();
			if (error == 2){
				break;
			}
		}
        if(v==1){printf("#RUN_DONE\n");}
		run += 1;
		if (run >= runs && runs > 0){
			break;
		}
    }
    cleanup_platform();
    return error;
}


int do_test_run(){
    int error = hardware_test();

    if(v==2){printf("\nEnded %d\n", error);}

    if (error != 0){
    	if(v==2){printf("\nError: %d ", error);}
    } else {
    	if(v==2){printf("\nRun Successful!: %d ", error);}
    }
    if (error == 1){
    	if(v==2){printf("Failed all tests.\n");}
    } else if (error == 2){
    	if(v==2){printf("Configuration failure.\n");}
    }
    return error;
}


int hardware_test(){
    int cases_to_test = TESTCASES;
    if (cases_to_test > TESTCASECOUNT || cases_to_test < 1){
    	cases_to_test = TESTCASECOUNT;
    	if (TESTCASES > 0){
    		if(v==2){printf("No enough test cases.. Running all %d cases\n", TESTCASECOUNT);}
    	}
    }
    if (algorithm == SUMPRODUCT){
    	if(v==2){printf("\nRunning Sum Product Algorithm");}
    } else if (algorithm == HARDDECISION) {
    	if(v==2){printf("\nRunning Hard Decision Algorithm");}
    }
    int errors = 0;
    if (runsingle <= 0) {
        for (int t = 0; t < cases_to_test; t++){
        	int tc = t + CASEOFFSET;
        	tc = tc % TESTCASECOUNT;

        	if(v==2){printf("\nTest #%d, Test case: %d, ", t+1, tc+1);}

            if (algorithm == SUMPRODUCT){
            	if(v==1){printf("#RESULT SPD %d ", tc+1);}
            } else if (algorithm == HARDDECISION) {
            	if(v==1){printf("#RESULT HDD %d ", tc+1);}
            }
            errors += run_case(*cases[tc]);
        }
        if (errors == cases_to_test){
        	if(v==2){printf("\nAll %d tests FAILED!\n", cases_to_test);}
        } else if (errors == 0){
        	if(v==2){printf("\nAll %d tests PASSED!\n", cases_to_test);}
        } else {
        	if(v==2){printf("\nTests PASSED: %3d/%d\n", cases_to_test-errors, cases_to_test);}
        	if(v==2){printf("Tests FAILED: %3d/%d\n", errors, cases_to_test);}
        }

    } else if (runsingle <= TESTCASECOUNT) {
    	if(v==2){printf("\nTest case: %d, ", runsingle);}
        errors += run_case(*cases[runsingle-1]);
        if (errors == 0) {
        	if(v==2){printf("\nTest passed!\n");}
        } else {
        	if(v==2){printf("\nTest failed!\n");}
        }
    }
    return 0;
}


int run_case(Testcase custard){
    // custard = case but cant use case as variable...

    //get binary message and initial errors..
    int errorsinmessage = 0;

    int i;
	for(i = 0; i < BLOCKSIZE; i++) {
		if (custard.receivedhard[i] != custard.GoldRef[i]) {
			errorsinmessage += 1;
		}
	}
	if(v==2){printf("SNR: %.1f, Flipped bits: %d.\n", custard.snr, errorsinmessage);}
	if(v==1){printf("%.1f %d ", custard.snr, errorsinmessage);}


    int itercount = 0;
    int *iterations = &itercount;

    int endsame = ENDSAME;

    unsigned int mx = MAXITER;
    long unsigned int output[BLOCKSIZE] = {0};

    XTime gbl_time_before_test;
    XTime gbl_time_after_test;

    if(v==2){printf("\nRunning...\n");}
    if (algorithm == SUMPRODUCT){
    	long unsigned int message[BLOCKSIZE];
        float_array_to_u32(custard.receivedfloat, message);
    	int snrxten = (int) (custard.snr * 10);


        XTime_GetTime(&gbl_time_before_test);
        run_sumProductDecoding(MAXITER, endsame, snrxten, message, output, iterations);
        XTime_GetTime(&gbl_time_after_test);

    } else if (algorithm == HARDDECISION) {

        XTime_GetTime(&gbl_time_before_test);
    	run_hardDecisionDecoding(mx, custard.receivedhard, output, iterations);
        XTime_GetTime(&gbl_time_after_test);
    }

    float time = (float) (gbl_time_after_test - gbl_time_before_test)/(COUNTS_PER_SECOND);
    if(v==2){printf("- Run took (%.4f) seconds\n", time);}
    if(v==1){printf("%.6f ", time);}


    if(v==1){printf("%d ", itercount);}
    if (itercount < 0){
    	if(v==2){printf("- Hardware maximum iterations reached. (%d)\n", -itercount);}
    }
    else if (itercount == 0){
    	if(v==2){printf("- Max iterations reached. (%d)\n", MAXITER);}
    } else {
    	if(v==2){printf("- Finished on iteration # %d.\n", itercount);}
    }
    int crcresult = -1;
    if (crc_bits[0] == 1) {
        crcresult = test_crc(output);
        if (crcresult == 1) {
        	if(v==2){printf("- CRC failed\n");}
        } else {
        	if(v==2){printf("- CRC succesfull\n");}
        }
    }

    int errors = 0;

    if(v==2){printf("- Comparing to GoldRef: ");}

    int goldrefresult = 0;
    for(i = 0; i < BLOCKSIZE; i++){
        if(output[i] != custard.GoldRef[i]){
            errors += 1;
            goldrefresult = 1;
        }
    }
    if (errors > 0){
    	if(v==2){printf("Fail! (%d errors.)\n", errors);}
    } else {
    	if(v==2){printf("OK!\n");}
    }

    if(v==1){printf("%d %d\n", crcresult, errors);}

    if (crcresult == -1) {
        return goldrefresult;
    } else {
        if (crcresult != goldrefresult){
            if (crcresult == 1){
            	if(v==2){printf("  - CRC gave false negative!\n");}
            } else {
            	if(v==2){printf("  - CRC gave false positive!\n");}
            }
        }
        return crcresult;
    }
}

int test_crc(long unsigned int output[BLOCKSIZE]){
    int crc_padded_len = MSGLEN + CRCLEN - 1;
    short unsigned  test[BLOCKSIZE] = {0};
    int c = 0;
    int i;

    for (i = 0; i < crc_padded_len; ++i){
        test[i] = output[i];
    }

    while (c < MSGLEN){
        for(i = c; i < MSGLEN; ++i){
            if (test[i] == 1){
                c = i;
                break;
            }
            c = -1;
        }
        if (c == -1){
            break;
        }
        for(i = 0; i < CRCLEN; ++i){
            test[c+i] ^= crc_bits[i];
        }
    }
    for (i = 0; i < crc_padded_len; ++i){
        if (test[i] == 1){
            return 1;
        }
    }
    return 0;
}

int run_sumProductDecoding(unsigned int max_iter, unsigned int endsame, unsigned int snrxten, long unsigned int * message, long unsigned int * output, int * iterations) {
    int status;
	doSumproductdecoding_cfg = XSumproductdecoding_LookupConfig(XPAR_SUMPRODUCTDECODING_0_DEVICE_ID);
	if (!doSumproductdecoding_cfg) {
		if(v==2){printf("Error loading conf for spd\n");}
		return 2;
	}
	status = XSumproductdecoding_CfgInitialize(&doSumproductdecoding, doSumproductdecoding_cfg);
	if (status != XST_SUCCESS){
		if(v==2){printf("Error initializing spd\n");}
		return 2;
	}
	if(v==2){printf("- Writing to board..\n");}
    XSumproductdecoding_Set_max_iter(&doSumproductdecoding, max_iter);
    XSumproductdecoding_Set_endsame(&doSumproductdecoding, endsame);
    XSumproductdecoding_Set_snrxten(&doSumproductdecoding, snrxten);
    XSumproductdecoding_Write_message_Words(&doSumproductdecoding, 0, message, BLOCKSIZE);
    XSumproductdecoding_Write_decodedmsg_Words(&doSumproductdecoding, 0, output, BLOCKSIZE);

    XSumproductdecoding_Start(&doSumproductdecoding);
    while(!XSumproductdecoding_IsDone(&doSumproductdecoding));

    XSumproductdecoding_Read_decodedmsg_Words(&doSumproductdecoding, 0, output, BLOCKSIZE);
    unsigned int iter = XSumproductdecoding_Get_iterations(&doSumproductdecoding);
    *iterations = (int) iter;
    return 0;
}


int run_hardDecisionDecoding(unsigned int max_iter, long unsigned int * message, long unsigned int * output, int *iterations){
    int status;
    doHarddecisiondecoding_cfg = XHarddecisiondecoding_LookupConfig(XPAR_HARDDECISIONDECODING_0_DEVICE_ID);
    if (!doHarddecisiondecoding_cfg) {
    	if(v==2){printf("Error loading conf for hdd\n");}
        return 2;
    }
    status = XHarddecisiondecoding_CfgInitialize(&doHarddecisiondecoding, doHarddecisiondecoding_cfg);
    if (status != XST_SUCCESS){
    	if(v==2){printf("Error initializing hdd\n");}
        return 2;
    }
    if(v==2){printf("- Writing to board..\n");}
    XHarddecisiondecoding_Set_max_iter(&doHarddecisiondecoding, max_iter);
    XHarddecisiondecoding_Write_message_Words(&doHarddecisiondecoding, 0, message, BLOCKSIZE);
    XHarddecisiondecoding_Write_output_r_Words(&doHarddecisiondecoding, 0, output, BLOCKSIZE);

    XHarddecisiondecoding_Start(&doHarddecisiondecoding);
    while(!XHarddecisiondecoding_IsDone(&doHarddecisiondecoding));

    XHarddecisiondecoding_Read_output_r_Words(&doHarddecisiondecoding, 0, output, BLOCKSIZE);
    unsigned int iter = XHarddecisiondecoding_Get_iterations(&doHarddecisiondecoding);
    *iterations = (int) iter;
    return 0;
}



void float_array_to_u32(float input[BLOCKSIZE], long unsigned int *result) {
    for (int i = 0; i < BLOCKSIZE; ++i){
        result[i] = float_to_u32(input[i]);
    }
}


long unsigned int float_to_u32(float val){
    unsigned int result;
    union float_bytes {
        float v;
        unsigned char bytes[4];
    }data;
    data.v = val;
    result = (data.bytes[3] << 24) + (data.bytes[2] << 16) + (data.bytes[1] << 8) + (data.bytes[0]);
    return result;
}
