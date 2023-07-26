# -*- coding: utf-8 -*-
# @Time:  18:49
# @Author: tk
# @File：evaluate
import torch
from aigc_zoo.utils.streamgenerator import GenTextStreamer
from deep_training.data_helper import ModelArguments, DataArguments,DataHelper
from transformers import HfArgumentParser, BitsAndBytesConfig
from aigc_zoo.model_zoo.internlm.llm_model import MyTransformer,InternLMConfig,InternLMTokenizer,InternLMForCausalLM
from aigc_zoo.utils.llm_generate import Generate
from serving.model_handler.base import EngineAPI_Base
from config.constant_map import models_info_args
from serving.model_handler.base.data_define import ChunkData


class NN_DataHelper(DataHelper):pass


class EngineAPI(EngineAPI_Base):
    def init_model(self,device_id=None):
        parser = HfArgumentParser((ModelArguments,))
        (model_args,) = parser.parse_dict(self.model_config_dict["model_config"], allow_extra_keys=True)

        dataHelper = NN_DataHelper(model_args)
        tokenizer, config, _, _ = dataHelper.load_tokenizer_and_config(config_class_name=InternLMConfig,
                                                                       tokenizer_class_name=InternLMTokenizer)
        config.pad_token_id = config.eos_token_id

        pl_model = MyTransformer(config=config, model_args=model_args,
                                 torch_dtype=torch.float16, )

        model = pl_model.get_llm_model()
        model = model.eval()
        model.requires_grad_(False)

        model = model.half()
        if device_id is None:
            model.cuda()
        else:
            model.cuda(device_id)

        self.model: InternLMForCausalLM = model
        self.tokenizer = tokenizer


    @torch.no_grad()
    def _generate(self,  query: str,do_sample=True, top_p=0.7, temperature=0.95, logits_processor=None, **kwargs):
        gen_kwargs = {"do_sample": do_sample, "top_p": top_p,  "eos_token_id": [2, 103028],
                      "repetition_penalty" : 1.01,
                      "temperature": temperature, "logits_processor": logits_processor, **kwargs}
        output_scores = gen_kwargs.get('output_scores', False)
        if output_scores:
            gen_kwargs['return_dict_in_generate'] = True
        # prompt = "Human：" + query + "\nAssistant："
        # 自行加模板
        prompt = query
        inputs = self.tokenizer([prompt], return_tensors="pt")
        inputs = inputs.to(self.model.device)
        outputs = self.model.generate(**inputs, **gen_kwargs)
        if output_scores:
            score = outputs.scores[0]
            return score
        outputs = outputs.tolist()[0][len(inputs["input_ids"][0]):]
        response = self.tokenizer.decode(outputs)
        return response

    def chat_stream(self, query, n,gtype='total', history=None, **kwargs):
        if history is None:
            history = []

        default_kwargs = dict(history=history, eos_token_id=[2, 103028],
                              do_sample=True, top_p=0.7, temperature=0.95,
                              repetition_penalty=1.01,
                              )

        default_kwargs.update(kwargs)

        chunk = ChunkData()
        def process_token_fn(text, stream_end, chunk: ChunkData):
            chunk.text += text
            chunk.idx += 1
            if chunk.idx % n == 0 or stream_end or chunk.idx == 1:
                if gtype == 'total':
                    self.push_response(((chunk.text, history), 0, "ok", False))
                    chunk.idx = 0
                else:
                    self.push_response(((chunk.text, history), 0, "ok", False))
                    chunk.clear()

        streamer = GenTextStreamer(process_token_fn, chunk, tokenizer=self.tokenizer)
        _ = self.get_model().chat( tokenizer=self.tokenizer, streamer=streamer, query=query, **default_kwargs)
        if gtype == 'total':
            self.push_response((('', history), 0, "ok", True))
        else:
            self.push_response(((chunk.text, history), 0, "ok", True))
        return None


    def chat(self, query,history=None, **kwargs):
        if history is None:
            history = []

        default_kwargs = dict(history=history,eos_token_id=[2, 103028],
                              do_sample=True, top_p=0.7, temperature=0.95,
                              repetition_penalty=1.01,
                              )
        default_kwargs.update(kwargs)
        response, history = self.model.chat(self.tokenizer, query=query, **default_kwargs)
        return response, history

    def generate(self,input,**kwargs):
        default_kwargs = dict(eos_token_id = [2, 103028],
            do_sample=True, top_p=0.7, temperature=0.95,
            repetition_penalty=1.01,
        )
        default_kwargs.update(kwargs)
        output = self.model.chat(self.tokenizer, query=input, **default_kwargs)
        output_scores = default_kwargs.get('output_scores', False)
        if output_scores:
            return output
        response, history = output
        return response


if __name__ == '__main__':
    api_client = EngineAPI(models_info_args['internlm-chat-7b'])
    api_client.init()
    text_list = ["写一个诗歌，关于冬天",
                 "晚上睡不着应该怎么办",
                 "从南京到上海的路线",
                 "登鹳雀楼->王之涣\n夜雨寄北->",
                 "Hamlet->Shakespeare\nOne Hundred Years of Solitude->",
                 ]
    for input in text_list:
        response = api_client.generate(input)
        print('input', input)
        print('output', response)
