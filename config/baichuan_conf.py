# -*- coding: utf-8 -*-
# @Author  : ssbuild
# @Time    : 2023/8/2 10:40


baichuan_config = {
    "baichuan-7B": {
        "enable": False,
        "work_mode": "deepspeed",  # one of deepspeed,accelerate,hf
        "workers": [
            {
                "device_id": [0]  # 默认启动一个worker , 使用第一块显卡
            }
        ],
        "auto_quantize": False, # 是否自动量化模型
        "model_config": {
            "model_type": "baichuan",
            "model_name_or_path": "/data/nlp/pre_models/torch/baichuan/baichuan-7B",
            "use_fast_tokenizer": False,
            "do_lower_case": None,
            "lora": {
                # 多个 lora , adapter_name: lora weight dir
                # "default": "/data/nlp/pre_models/torch/lora_path_dir",
                # "your_adapter_name": "/data/nlp/pre_models/torch/your_adapter_dir",
            }
        }
    },

    "Baichuan-13B-Chat": {
        "enable": False,
        "work_mode": "deepspeed",  # one of deepspeed,accelerate,hf
        "workers": [
            {
                "device_id": [0]  # 默认启动一个worker , 使用第一块显卡
            }
        ],
        "auto_quantize": False, # 是否自动量化模型
        "model_config": {
            "model_type": "baichuan",
            "model_name_or_path": "/data/nlp/pre_models/torch/baichuan/Baichuan-13B-Chat",
            "use_fast_tokenizer": False,
            "do_lower_case": None,
            "lora": {
                # 多个 lora , adapter_name: lora weight dir
                # "default": "/data/nlp/pre_models/torch/lora_path_dir",
                # "your_adapter_name": "/data/nlp/pre_models/torch/your_adapter_dir",
            }
        }
    },
    "baichuan-13b-chat-int4": {
        "enable": True,
        "work_mode": "deepspeed",  # one of deepspeed,accelerate,hf
        "workers": [
            {
                "device_id": [0]  # 默认启动一个worker , 使用第一块显卡
            }
        ],

        "auto_quantize": False, # 是否自动量化模型
        "model_config": {
            "model_type": "baichuan",
            "model_name_or_path": "/data/nlp/pre_models/torch/baichuan2/baichuan-13b-chat-int4",
            "use_fast_tokenizer": False,
            "do_lower_case": None,
            "lora": {
                # 多个 lora , adapter_name: lora weight dir
                # "default": "/data/nlp/pre_models/torch/lora_path_dir",
                # "your_adapter_name": "/data/nlp/pre_models/torch/your_adapter_dir",
            }
        }
    },
}