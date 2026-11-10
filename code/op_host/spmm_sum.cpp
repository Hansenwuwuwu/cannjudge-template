// Host侧Tiling实现
#include "register/op_def_registry.h"
#include "tiling/platform/platform_ascendc.h"

#include "../op_kernel/spmm_sum_tiling.h"
#include "../op_kernel/tiling_key_spmm_sum.h"

namespace optiling {
    static ge::graphStatus TilingFunc(gert::TilingContext *context) {
        // 示例: 获取平台信息
        auto platform = platform_ascendc::PlatformAscendC(context->GetPlatformInfo());
        int32_t num_cores_aiv = platform.GetCoreNumAiv();
        uint64_t ub_size;
        platform.GetCoreMemSize(platform_ascendc::CoreMemType::UB, ub_size);
        // 示例: 获取算子输入数组信息
        const gert::Tensor* tensor_rowptr = context->GetRequiredInputTensor(0);
        const gert::Tensor* tensor_col = context->GetRequiredInputTensor(1);
        const gert::Tensor* tensor_value = context->GetRequiredInputTensor(2);
        const gert::Tensor* tensor_mat = context->GetRequiredInputTensor(3);
        ge::DataType dtype_value = tensor_value->GetDataType(); // 获取数据类型
        int dtype_size_value = ge::GetSizeByDataType(dtype_value); // 获取数据类型的字长
        uint32_t length_value = tensor_value->GetShapeSize(); // 获取元素个数
        uint32_t size_value = tensor_value->GetSize(); // 获取内存大小
        // 示例: 配置tiling key, 从而实现kernel侧不同数据类型/算法的区分
        uint32_t DT_VALUE = static_cast<uint32_t>(dtype_value);
        ASCENDC_TPL_SEL_PARAM(context, DT_VALUE);
        // 示例: 计算tiling方案并填充tiling结构体
        SpmmSumTilingData* tiling = context->GetTilingData<SpmmSumTilingData>();
        tiling->length = length_value;
        // 配置启动核数
        context->SetBlockDim(num_cores_aiv);
        // 配置workspace大小
        size_t *currentWorkspace = context->GetWorkspaceSizes(1);
        currentWorkspace[0] = 0;
        return ge::GRAPH_SUCCESS;
    }
}  // namespace optiling

namespace ge {
    static graphStatus InferShape(gert::InferShapeContext *context) {
        return GRAPH_SUCCESS;
    }
    static graphStatus InferDataType(gert::InferDataTypeContext *context) {
        return ge::GRAPH_SUCCESS;
    }
}  // namespace ge

namespace ops {
    class SpmmSum : public OpDef {
    public:
        explicit SpmmSum(const char *name) : OpDef(name) {
            this->Input("rowptr")
                .ParamType(REQUIRED)
                .DataType({ge::DT_INT64, ge::DT_INT64})
                .Format({ge::FORMAT_ND, ge::FORMAT_ND});
            this->Input("col")
                .ParamType(REQUIRED)
                .DataType({ge::DT_INT32, ge::DT_INT32})
                .Format({ge::FORMAT_ND, ge::FORMAT_ND});
            this->Input("value")
                .ParamType(REQUIRED)
                .DataType({ge::DT_FLOAT, ge::DT_FLOAT16})
                .Format({ge::FORMAT_ND, ge::FORMAT_ND});
            this->Input("mat")
                .ParamType(REQUIRED)
                .DataType({ge::DT_FLOAT, ge::DT_FLOAT16})
                .Format({ge::FORMAT_ND, ge::FORMAT_ND});
            this->Output("out")
                .ParamType(REQUIRED)
                .DataType({ge::DT_FLOAT, ge::DT_FLOAT16})
                .Format({ge::FORMAT_ND, ge::FORMAT_ND});
            this->SetInferShape(ge::InferShape).SetInferDataType(ge::InferDataType);
            this->AICore()
                .SetTiling(optiling::TilingFunc)
                .AddConfig("ascend910b");
        }
    };
    OP_ADD(SpmmSum);
}  // namespace ops
