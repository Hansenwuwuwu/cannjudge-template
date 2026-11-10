#include <acl/acl.h>
#include <aclnn/acl_meta.h>
#ifndef R27_HEADER
#define R27_HEADER "aclnn_swi_glu_current_audit.h"
#define R27_GET aclnnSwiGluCurrentAuditGetWorkspaceSize
#define R27_API aclnnSwiGluCurrentAudit
#define R27_ENTRY "aclnnSwiGluCurrentAudit"
#endif
#include R27_HEADER
#include <dlfcn.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static void Check(int code,const char *what){if(code)throw std::runtime_error(std::string(what)+": "+std::to_string(code));}
#define CHECK(x) Check((x),#x)
struct Resources {
    bool initialized=false,device=false;
    aclrtStream stream=nullptr;
    aclOpExecutor *executor=nullptr;
    std::vector<void *> allocations;
    std::vector<aclrtEvent> events;
    std::vector<aclTensor *> tensors;
    struct Snapshot{void *pointer;std::vector<uint16_t> data;};
    std::vector<Snapshot> snapshots;
    ~Resources(){
        if(stream)(void)aclrtSynchronizeStreamWithTimeout(stream,3000);
        if(executor)(void)aclDestroyAclOpExecutor(executor);
        for(auto event:events)(void)aclrtDestroyEvent(event);
        for(auto *t:tensors)(void)aclDestroyTensor(t);
        for(auto *p:allocations)(void)aclrtFree(p);
        if(stream)(void)aclrtDestroyStream(stream);
        if(device)(void)aclrtResetDevice(0);
        if(initialized)(void)aclFinalize();
    }
    void *Allocate(size_t bytes){void *p=nullptr;CHECK(aclrtMalloc(&p,bytes,ACL_MEM_MALLOC_HUGE_FIRST));allocations.push_back(p);return p;}
    aclTensor *Tensor(void *pointer,const std::vector<int64_t>&shape,aclDataType type=ACL_FLOAT16){
        std::vector<int64_t> strides(shape.size(),1);
        for(size_t i=shape.size();i>1;--i)strides[i-2]=strides[i-1]*shape[i-1];
        auto *t=aclCreateTensor(shape.data(),shape.size(),type,strides.data(),0,ACL_FORMAT_ND,shape.data(),shape.size(),pointer);
        if(!t)throw std::runtime_error("aclCreateTensor failed");
        tensors.push_back(t);return t;
    }
    aclTensor *Input(const std::string&path,const std::vector<int64_t>&shape,aclDataType type=ACL_FLOAT16){
        size_t count=1;for(auto n:shape)count*=static_cast<size_t>(n);
        const size_t bytes=count*(type==ACL_FLOAT?4:2);
        std::ifstream f(path,std::ios::binary|std::ios::ate);
        if(!f || f.tellg()!=static_cast<std::streamsize>(bytes))throw std::runtime_error("wrong input size "+path);
        std::vector<uint16_t> data(bytes/2);f.seekg(0);
        if(!f.read(reinterpret_cast<char*>(data.data()),bytes))throw std::runtime_error("input read failed");
        void *p=Allocate(bytes);CHECK(aclrtMemcpy(p,bytes,data.data(),bytes,ACL_MEMCPY_HOST_TO_DEVICE));
        snapshots.push_back({p,std::move(data)});return Tensor(p,shape,type);
    }
    void VerifyInputs(){
        for(const auto&s:snapshots){size_t bytes=s.data.size()*2;std::vector<uint16_t> after(s.data.size());
            CHECK(aclrtMemcpy(after.data(),bytes,s.pointer,bytes,ACL_MEMCPY_DEVICE_TO_HOST));
            if(std::memcmp(after.data(),s.data.data(),bytes))throw std::runtime_error("input modified");}
    }
};
static void Write(const std::string&path,const uint8_t *data,size_t bytes){
    std::ofstream f(path,std::ios::binary);if(!f.write(reinterpret_cast<const char*>(data),bytes))throw std::runtime_error("write failed "+path);
}
static bool Guard(const std::vector<uint8_t>&v,size_t n,int fill){
    return std::all_of(v.begin(),v.begin()+n,[fill](uint8_t x){return x==fill;}) &&
           std::all_of(v.end()-n,v.end(),[fill](uint8_t x){return x==fill;});
}
int main(int argc,char **argv){
    std::cout<<std::unitbuf;
    const bool sequence=false;
    if(!sequence && argc!=8){std::cerr<<"usage: runner CASE OUT SHAPE LIB ENTRY REPEAT PREFILL; or --mode-sequence CASE OUT R27_SO R26_SO\n";return 2;}
    Resources r;
    try{
        std::string source=argv[sequence?2:1],out=argv[sequence?3:2];
        const char *lib=argv[4];
        std::vector<int64_t> shape;std::stringstream input(sequence?"64,256":argv[3]);std::string part;
        while(std::getline(input,part,',')){int64_t n=std::stoll(part);if(n<=0)throw std::runtime_error("nonpositive shape");shape.push_back(n);}
        if(shape.empty())throw std::runtime_error("empty shape");
        uint64_t elements=1;for(auto n:shape){if(elements>SIZE_MAX/(2*uint64_t(n)))throw std::runtime_error("shape overflow");elements*=n;}
        const int64_t d=shape.back();const int repeat=sequence?2:std::stoi(argv[6]),initialFill=sequence?90:std::stoi(argv[7]);
        if((!sequence && (repeat<1 || repeat>64))||initialFill<0||initialFill>255)throw std::runtime_error("unsupported repeat/prefill");
        std::string entry=sequence?R27_ENTRY:argv[5];if(entry!=R27_ENTRY)throw std::runtime_error("entry differs from generated ABI");
        CHECK(aclInit(nullptr));r.initialized=true;
        void *library=dlopen(lib,RTLD_NOW|RTLD_LOCAL);if(!library)throw std::runtime_error(dlerror());
        // CANN may snapshot tiling registries at the first executor; register
        // both libraries before any call, without executing the off control yet.
        if(sequence && !dlopen(argv[5],RTLD_NOW|RTLD_LOCAL))throw std::runtime_error(dlerror());
        auto get=reinterpret_cast<decltype(&R27_GET)>(dlsym(library,(entry+"GetWorkspaceSize").c_str()));
        auto run=reinterpret_cast<decltype(&R27_API)>(dlsym(library,entry.c_str()));
        if(!get||!run)throw std::runtime_error("generated symbols absent");
        Dl_info info{};if(!dladdr(reinterpret_cast<void*>(get),&info)||!info.dli_fname)throw std::runtime_error("dladdr failed");
        std::cout<<"resolved_opapi="<<info.dli_fname<<" entry="<<entry<<"\n";
        uint32_t count=0;CHECK(aclrtGetDeviceCount(&count));std::cout<<"visible_devices="<<count<<" logical_device=0\n";if(count!=1)throw std::runtime_error("expected one visible device");CHECK(aclrtSetDevice(0));r.device=true;CHECK(aclrtCreateStream(&r.stream));
        std::filesystem::create_directories(out);
        auto *x=r.Input(source+"/input_x.bin",shape);
        auto *w1=r.Input(source+"/weight_1.bin",{d,d});auto *b1=r.Input(source+"/bias_1.bin",{d});
        auto *w2=r.Input(source+"/weight_2.bin",{d,d});auto *b2=r.Input(source+"/bias_2.bin",{d});
        size_t bytes=elements*2;auto *outputBase=static_cast<uint8_t*>(r.Allocate(bytes+64));
        auto *y=r.Tensor(outputBase+32,shape);
        aclrtEvent startEvent=nullptr,endEvent=nullptr;
        CHECK(aclrtCreateEvent(&startEvent));r.events.push_back(startEvent);
        CHECK(aclrtCreateEvent(&endEvent));r.events.push_back(endEvent);
        uint8_t *workspaceBase=nullptr;uint64_t capacity=0;
        const int fills[3]={90,165,60};
        for(int iteration=0;iteration<repeat;++iteration){
            int fill=repeat==1?initialFill:fills[iteration%3];
            std::string target=out;
            std::filesystem::create_directories(target);
            CHECK(aclrtMemset(outputBase,bytes+64,fill,bytes+64));
            uint64_t workspaceBytes=0;CHECK(get(x,w1,b1,w2,b2,y,&workspaceBytes,&r.executor));
            if(!r.executor||workspaceBytes>SIZE_MAX-1024)throw std::runtime_error("invalid executor/workspace");
            if(!workspaceBase){capacity=workspaceBytes;workspaceBase=static_cast<uint8_t*>(r.Allocate(capacity+1024));}
            if(capacity!=workspaceBytes)throw std::runtime_error("workspace size changed on reuse");
            CHECK(aclrtMemset(workspaceBase,capacity+1024,fill,capacity+1024));
            auto start=std::chrono::steady_clock::now();
            CHECK(aclrtRecordEvent(startEvent,r.stream));
            CHECK(run(workspaceBase+512,workspaceBytes,r.executor,r.stream));
            CHECK(aclrtRecordEvent(endEvent,r.stream));
            CHECK(aclrtSynchronizeStreamWithTimeout(r.stream,3000));
            auto stop=std::chrono::steady_clock::now();float deviceMs=0;
            CHECK(aclrtEventElapsedTime(&deviceMs,startEvent,endEvent));
            std::vector<uint8_t> output(bytes+64),workspace(1024);
            CHECK(aclrtMemcpy(output.data(),output.size(),outputBase,output.size(),ACL_MEMCPY_DEVICE_TO_HOST));
            CHECK(aclrtMemcpy(workspace.data(),512,workspaceBase,512,ACL_MEMCPY_DEVICE_TO_HOST));
            CHECK(aclrtMemcpy(workspace.data()+512,512,workspaceBase+workspaceBytes+512,512,ACL_MEMCPY_DEVICE_TO_HOST));
            Write(target+"/output_f16.bin",output.data()+32,bytes);
            if(iteration==repeat-1){
                std::vector<uint8_t> last(workspaceBytes);
                CHECK(aclrtMemcpy(last.data(),last.size(),workspaceBase+512,last.size(),ACL_MEMCPY_DEVICE_TO_HOST));
                Write(target+"/workspace_last.bin",last.data(),last.size());
            }
            if(!Guard(output,32,fill)||!Guard(workspace,512,fill))throw std::runtime_error("guard corrupted; raw data untrusted");
            r.VerifyInputs();
            double wall=std::chrono::duration<double,std::micro>(stop-start).count();
            std::ofstream record(target+"/iteration_"+std::to_string(iteration)+".json");
            record<<"{\"iteration\":"<<iteration<<",\"prefill\":"<<fill<<",\"guards\":\"OK\",\"inputs_immutable\":\"OK\",\"wall_us\":"<<wall<<",\"device_ms\":"<<deviceMs<<",\"workspaceBytes\":"<<workspaceBytes<<"}\n";
            if(!record)throw std::runtime_error("iteration record write failed");
            std::ofstream checks(target+"/checks.json");
            checks<<"{\"guards\":true,\"inputs_immutable\":true}\n";
            if(!checks)throw std::runtime_error("checks write failed");
            CHECK(aclDestroyAclOpExecutor(r.executor));r.executor=nullptr;
            std::cout<<"R27_RUN_OK workspaceBytes="<<workspaceBytes<<" prefill="<<fill<<" guards=OK inputs_immutable=OK wall_us="<<wall<<" device_ms="<<deviceMs<<"\n";
        }
        return 0;
    }catch(const std::exception&e){std::cerr<<"R27_RUN_ERROR "<<e.what()<<"\n";return 1;}
}
