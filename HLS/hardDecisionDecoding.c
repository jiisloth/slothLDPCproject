#include "hmatrix.h"


#define HARDMAXITER 32



void hardDecisionDecoding(int max_iter, int message[BLOCKSIZE], int output[BLOCKSIZE], int *iterations){

#pragma HLS INTERFACE mode=s_axilite port=iterations
#pragma HLS INTERFACE mode=s_axilite port=output
#pragma HLS INTERFACE mode=s_axilite port=message
#pragma HLS INTERFACE mode=s_axilite port=max_iter
#pragma HLS INTERFACE mode=s_axilite port=return


    int c;
    int i;
    int j;

    int maxi = max_iter;
    int itercount = 0;

    int v_nodes[BLOCKSIZE];
    int decode[BLOCKSIZE];
	const float vote_divider = (float)(PARITYCHECKS+1)/2.0;

    for (j = 0; j < BLOCKSIZE; ++j) {
    	decode[j] = message[j];
        v_nodes[j] = decode[j];
    }



    for (int iter = 0; iter < HARDMAXITER; ++iter) {
    	if (iter < maxi){
    	    int satisfied = 0;
            for (c = 0; c < CNODES; ++c) {
                int c_node = 0;
                for (i = 0; i < PARITYCHECKS; ++i) {
                	for (j = 0; j < BLOCKSIZE; ++j) {
                        if (h_matrix[j][i] == c) {
                            c_node ^= decode[j];
                        }
                    }
                }
                satisfied |= c_node;
                for (i = 0; i < PARITYCHECKS; ++i) {
                	for (j = 0; j < BLOCKSIZE; ++j) {
                        if (h_matrix[j][i] == c) {
                            v_nodes[j] += decode[j]^c_node;
                        }
                    }
                }
            }

            if (satisfied == 0){
                itercount = iter +1;
                break;
            }

            for (j = 0; j < BLOCKSIZE; ++j) {
                if (v_nodes[j] > vote_divider){
                	decode[j] = 1;
                } else if (v_nodes[j] < vote_divider){
                	decode[j] = 0;
                }
                v_nodes[j] = decode[j];
            }
    	}
    }
    // set end values.
	if (itercount == 0 && maxi > HARDMAXITER){
		// Tells that Hard max was reached.
		itercount = -HARDMAXITER;
	}
    *iterations = itercount;
    for (j = 0; j < BLOCKSIZE; ++j) {
    	output[j] = decode[j];
    }
}
