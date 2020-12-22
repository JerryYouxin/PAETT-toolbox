#include <energy_utils.h>
#include <sys/time.h>
#include <unistd.h>
#include <errno.h>
// #include <libgen.h>
#include <string>
uint64_t get_time() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec*1000000 + tv.tv_usec;
}

void usage() {
    printf("Usage: collect_energy [-a <#warmup> <#evaluation>] <exe> <args>");
}

int main(int argc, char* argv[]) {
    int k = 1;
    int num_warm = 0;
    int num_eval = 1;
    while(k<argc && argv[k][0]=='-') {
        std::string arg(argv[k]);
        if(arg=="-a") {
            num_warm = atoi(argv[k+1]);
            num_eval = atoi(argv[k+2]);
            k += 3;
        } else {
            usage();
            exit(1);
        }
    }
    if(k<=1 || argc<=1) {
        usage();
        return 1;
    }
    if(energy_init()!=0) {
        printf("Energy Collection Initialization Failed!\n");
        exit(1);
    }
    printf("Redirecting standard output to stdout.log\n");
    // char** _argv = malloc(sizeof(char*)*argc);
    // _argv[0] = basename(argv[1]);
    // for(int i=1;i<argc-1;++i) {
    //     _argv[i] = argv[i+1];
    // }
    // _argv[argc-1] = NULL;
    std::string command(argv[k]);
    for(int i=k; i<argc-1; ++i) {
        command += " ";
        command += argv[i+1];
    }
    command += " > stdout.log";
    printf("Warming up %d times ...\n", num_warm);
    printf("Process: 0%%\r");
    fflush(stdout);
    for(int i=0;i<num_warm;++i) {
        system(command.c_str());
        printf("Process: %.2f%%\r", 100*(float)(i+1)/(float)num_warm);
        fflush(stdout);
    }
    printf("\nFinish Warm up, Now evaluate for %d times ...\n", num_eval);
    printf("Process: 0%%\r");
    fflush(stdout);
    double energy = 0;
    double time = 0;
    for(int i=0;i<num_eval;++i) {
        double init_energy = get_pkg_energy();
        uint64_t init_time = get_time();
        /* == Running == */
        system(command.c_str());
        /* ============= */
        uint64_t fini_time = get_time();
        double fini_energy = get_pkg_energy();
        energy+= fini_energy-init_energy;
        time  += (double)(fini_time-init_time)/(double)1e6;
        printf("Process: %.2f %%: energy=%.2lf, time=%.2lf\r", 100*(float)(i+1)/(float)num_eval, energy/(double)(i+1), time/(double)(i+1));
        fflush(stdout);
    }
    printf("\n");
    energy/= num_eval;
    time  /= num_eval;
    printf("Total Energy: %lf Joules\n", energy);
    printf("Total Time : %lf Seconds\n", time);
    FILE* fp = fopen("collect_energy.log", "w");
    if(fp==NULL) {
        printf("Failed to open collect_energy.log for record\n");
    } else {
        fprintf(fp, "%lf,%lf", energy, time);
        fclose(fp);
    }
    // free(_argv);
    energy_finalize();
    return 0;
}