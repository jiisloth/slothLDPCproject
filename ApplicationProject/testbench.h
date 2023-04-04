int run_sumProductDecoding(unsigned int max_iter, unsigned int endsame, unsigned int snrxten, long unsigned int * message, long unsigned int * decodedmsg, int *iterations);
int run_hardDecisionDecoding(unsigned int max_iter, long unsigned int * message, long unsigned int * output, int *iterations);

int run_case(Testcase custard);
int hardware_test();
int do_test_run();
int test_crc(long unsigned int output[BLOCKSIZE]);

long unsigned int float_to_u32(float val);
void float_array_to_u32(float input[BLOCKSIZE], long unsigned int *result);


#define SUMPRODUCT 0
#define HARDDECISION 1
