#include <stdio.h>
#include "platform.h"
#include "xil_printf.h"


int main()
{
    init_platform();
    printf("\n");
    printf("###########################\n");
    printf("## Board Reset Complete! ##\n");
    printf("###########################\n");
    printf("\n");
    cleanup_platform();
    return 0;
}
