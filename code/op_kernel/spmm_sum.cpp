// Kernel侧核函数实现
#include "kernel_operator.h"

#include "spmm_sum_tiling.h"
#include "tiling_key_spmm_sum.h"

template <class DT_VALUE>
class KernelSpmmSum {
public:
    __aicore__ inline KernelSpmmSum() {}
    __aicore__ inline void Init(GM_ADDR rowptr, GM_ADDR col, GM_ADDR value, GM_ADDR mat, GM_ADDR out, uint32_t length) {

    }
    __aicore__ inline void Process() {

    }
private:

};

template <typename DT_VALUE>
 __global__ __aicore__ void spmm_sum(GM_ADDR rowptr, GM_ADDR col, GM_ADDR value, GM_ADDR mat, GM_ADDR out, GM_ADDR workspace, GM_ADDR tiling) {
    REGISTER_TILING_DEFAULT(SpmmSumTilingData);
    GET_TILING_DATA_WITH_STRUCT(SpmmSumTilingData, tiling_data, tiling);
    KernelSpmmSum<DT_VALUE> op;
    op.Init(rowptr, col, value, mat, out, tiling_data.length);
    op.Process();
}
