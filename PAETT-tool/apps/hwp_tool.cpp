#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/types.h>
#include <unistd.h>

#define MSR_IA32_PM_ENABLE 0x770

#define MAX_CPUS	1024
int ncpu;
int msr_fd[MAX_CPUS];
static int open_msr_files(int mode) {
    int i;
    char filename[20];
    for(i=0;i<MAX_CPUS;++i) {
        sprintf(filename, "/dev/cpu/%d/msr", i);
        msr_fd[i] = open(filename, mode);
        if(msr_fd[i]<0) break;
    }
    ncpu = i;
    if(ncpu<=0) return -1;
    printf("** %d CPUs Detected\n",ncpu);
    return 0;
}

static void close_msr_files() {
    int i;
    for(i=0;i<ncpu;++i) {
        close(msr_fd[i]);
    }
}

#define CHECK(stmt) do { if(stmt!=0) {printf("%s Failed!\n",#stmt); exit(-1);} } while(0)
#define RESET_FD(fd) lseek(fd, 0, SEEK_SET)
int read_msr_by_idx(int dev_idx, off_t msr, uint64_t *val)
{
    int rc;
    int fileDescriptor = msr_fd[dev_idx];
    RESET_FD(fileDescriptor);
    rc = pread(fileDescriptor, (void*)val, (size_t)sizeof(uint64_t), msr);
    if (rc != sizeof(uint64_t))
    {
        printf("read_msr_by_idx(): Pread failed\n");
        return -1;
    }
    return 0;
}

inline int write_msr_by_idx(int dev_idx, off_t msr, uint64_t val)
{
    int rc;
    int fileDescriptor = msr_fd[dev_idx];
    RESET_FD(fileDescriptor);
    rc = pwrite(fileDescriptor, &val, (size_t)sizeof(uint64_t), msr);
    if (rc != sizeof(uint64_t))
    {
        printf("write_msr_by_idx(): Pwrite failed\n");
        return -1;
    }
    return 0;
}

void hwp_query() {
    CHECK(open_msr_files(O_RDONLY));
    int i; uint64_t val;
    bool allEnabled = true;
    printf("HWP Status:\n\t");
    for(i=0;i<ncpu;++i) {
        CHECK(read_msr_by_idx(i, MSR_IA32_PM_ENABLE, &val));
        printf("%d ", val);
        allEnabled = allEnabled && (!!val);
    }
    printf("\nAll HWP Enabled: %s\n",allEnabled?"true":"false");
    close_msr_files();
}

void hwp_enable() {
    int i;
    CHECK(open_msr_files(O_RDWR));
    for(i=0;i<ncpu;++i) {
        CHECK(write_msr_by_idx(i, MSR_IA32_PM_ENABLE, 1));
    }
    printf("HWP enabled\n");
    close_msr_files();
}

void hwp_disable() {
    int i;
    CHECK(open_msr_files(O_RDWR));
    for(i=0;i<ncpu;++i) {
        CHECK(write_msr_by_idx(i, MSR_IA32_PM_ENABLE, 0));
    }
    printf("HWP disabled\n");
    close_msr_files();
}

#define USAGE printf("Usage: hwp_tool [-q|-a|-d]\n\t-q\tquery HWP status (*default);\n\t-a\tEnable HWP;\n\t-d\tDisable HWP;\n");
int main(int argc,char *argv[]) {
    char mode;
    if(argc==2) {
        if(argv[1][0]!='-' && argv[1][1]!='\0' && argv[1][2]=='\0') {
            printf("Unknown arg: %s\n",argv[1]);
            goto fail;
        }
        mode = argv[1][1];
    } else if(argc==1) {
        mode = 'q';
    } else {
        printf("Error: Too much arguments!\n");
        goto fail;
    }
    switch (mode)
    {
    case 'q':
        hwp_query();
        break;
    case 'a':
        hwp_enable();
        break;
    case 'd':
        hwp_disable();
        break;
    
    default:
        printf("Unknown arg: %s\n",argv[1]);
        goto fail;
    }
    return 0;
fail:
    USAGE;
    return -1;
}