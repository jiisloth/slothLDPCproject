#include <math.h>
#include "hmatrix.h"


#define HARDMAXITER 32


void sumProductDecoding(int max_iter, int endsame, int snrxten, float message[BLOCKSIZE], int decodedmsg[BLOCKSIZE], int *iterations) {

#pragma HLS INTERFACE s_axilite port=iterations bundle=CTRLS
#pragma HLS INTERFACE s_axilite port=decodedmsg bundle=CTRLS
#pragma HLS INTERFACE s_axilite port=message bundle=CTRLS
#pragma HLS INTERFACE s_axilite port=snrxten bundle=CTRLS
#pragma HLS INTERFACE s_axilite port=endsame bundle=CTRLS
#pragma HLS INTERFACE s_axilite port=max_iter bundle=CTRLS
#pragma HLS INTERFACE s_axilite port=return bundle=CTRLS

    float prob0[BLOCKSIZE];
    float prob1[BLOCKSIZE];

    int bits[BLOCKSIZE];

    float deltaP[BLOCKSIZE][PARITYCHECKS];
#pragma HLS ARRAY_PARTITION dim=2 type=complete variable=deltaP


    int i = 0;
    int i2 = 0;
    int j = 0;
    int j2 = 0;

    int maxi = max_iter;
    int itercount = 0;

    float sigma = 1.0 + powf(10.0, (-(float)snrxten / 100.0)); //snrxten is 10 * snr

    // init arrays
    init:
	for (j = 0; j < BLOCKSIZE; ++j) {
        float prob = (float)(1 / (1 + expf((2 * message[j]) / sigma)));
        prob1[j] = prob;
        prob0[j] = (float)(1 - prob);

        //init msg.
        if (prob < 0.5){
        	bits[j] = 0;
        } else {
        	bits[j] = 1;
        }

        init_deltaP:
		for (i = 0; i < PARITYCHECKS; ++i) {
            // DeltaP - First time out of the main loop..
            deltaP[j][i] = 1 - prob - prob;
        }
    }

    int same = 0;
    int endonsames = endsame;

    // actual algorithm
    main_loop:
	for (int iter = 0; iter < HARDMAXITER; ++iter) {
    	if (iter < maxi){
    	    float Q0[BLOCKSIZE][PARITYCHECKS];
    	    float Q1[BLOCKSIZE][PARITYCHECKS];
			// Q:s
    	    float cnode_sum[CNODES];
//#pragma HLS ARRAY_PARTITION type=complete variable=cnode_sum
    	    initQ:
    	    for (int c = 0; c < CNODES; ++c){
    	    	cnode_sum[c] = 1;
    	    }
			Cj:
    	    for (j = 0; j < BLOCKSIZE; ++j){
				Ci:
				for (i = 0; i < PARITYCHECKS; ++i) {
#pragma HLS PIPELINE II=5
					cnode_sum[h_matrix[j][i]] *= deltaP[j][i];
				}
			}

			Qj:
			for (j = 0; j < BLOCKSIZE; ++j){
#pragma HLS PIPELINE II=3
				Qi:
				for (i = 0; i < PARITYCHECKS; ++i) {
					// Remove current j/i
					float  deltaQ = (float)(cnode_sum[h_matrix[j][i]]/deltaP[j][i]);
					Q0[j][i] = (float)(1.0+deltaQ);
					Q1[j][i] = (float)(1.0-deltaQ);
				}
			}
			// getting probabilities
			dPj:
			for (j = 0; j < BLOCKSIZE; ++j) {
#pragma HLS PIPELINE II=3
				dPi:
				for (i = 0; i < PARITYCHECKS; ++i) {
					float prob0matrix = prob0[j];
					float prob1matrix = prob1[j];
					pmi:
					for (i2 = 0; i2 < PARITYCHECKS; ++i2) {
						if (i != i2) {
							prob0matrix = (float)(prob0matrix * Q0[j][i2]);
							prob1matrix = (float)(prob1matrix * Q1[j][i2]);
						}
					}
					//scale
					float sum = (float)(prob0matrix + prob1matrix);
					if (sum != 0) {
						float factor = (float)(1 / sum);
						prob0matrix = (float)(prob0matrix * factor);
						prob1matrix = (float)(prob1matrix * factor);
					}
					//delta P
					deltaP[j][i] = prob0matrix - prob1matrix;
				}
			}
			//new P's
			pj:
			for (j = 0; j < BLOCKSIZE; ++j) {
				float p0 = prob0[j];
				float p1 = prob1[j];
				pi:
				for (i = 0; i < PARITYCHECKS; ++i) {
					pif:
					for ( i2 = 0; i2 < PARITYCHECKS; ++i2) {
#pragma HLS PIPELINE II=3
						p0 = (float)(p0 * Q0[j][i2]);
						p1 = (float)(p1 * Q1[j][i2]);
					}

				}
				//scale
				float sum = (float)(p0 + p1);
				if (sum != 0) {
					float factor = (float)(1 / sum);
					p0 = (float)(p0 * factor);
					p1 = (float)(p1 * factor);
				}
				prob0[j] = p0;
				prob1[j] = p1;

			}

			// Check ending conditions
		    int change = 0;
		    check_result:
			for (i = 0; i < BLOCKSIZE; ++i) {
		        if (prob0[i] > prob1[i]){
		            if (bits[i] == 1) {
		                change += 1;
		            }
		            bits[i] = 0;
		        } else {
		            if (bits[i] == 0) {
		                change += 1;
		            }
		            bits[i] = 1;
		        }
		    }
			// No changes
			if (change == 0){
				if (same >= endonsames-1){
					itercount = iter+1;
					break;
				}
				same = same + 1;
			} else {
				same = 0;
			}
    	}
    }
    // set end values.
	if (itercount == 0 && maxi > HARDMAXITER){
		// Tells that Hard max was reached.
		itercount = -HARDMAXITER;
	}
    *iterations = itercount;
    endloop:
	for (j = 0; j < BLOCKSIZE; ++j) {
        decodedmsg[j] = bits[j];
    }
}

