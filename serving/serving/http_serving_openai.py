# -*- coding: utf-8 -*-
# @Time:  23:32
# @Author: tk
# @File：http_serving_openai

import json
import logging
import traceback

from fastapi.openapi.models import HTTPBearer
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseSettings
from starlette.responses import StreamingResponse
import typing
from multiprocessing import Process
import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from starlette.middleware.cors import CORSMiddleware

from config.constant_map import models_info_args as model_config_map
from serving.openai_api.openai_api_protocol import ModelCard, ModelPermission, ModelList

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)



class AppSettings(BaseSettings):
    # The address of the model controller.
    api_keys: typing.List[str] = None

app_settings = AppSettings()
headers = {"User-Agent": "FastChat API Server"}
get_bearer_token = HTTPBearer(auto_error=False)

async def check_api_key(
    auth: typing.Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> str:
    if app_settings.api_keys:
        if auth is None or (token := auth.credentials) not in app_settings.api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    else:
        # api_keys not set; allow all
        return None

class HTTP_Serving(Process):
    def __init__(self,
                 queue_mapper: dict,
                 http_ip='0.0.0.0',
                 http_port=8088,
                 http_num_workers=1,
                 ):
        super().__init__(daemon=True)
        self.http_num_workers = http_num_workers
        self.http_ip = http_ip
        self.http_port = http_port
        self.queue_mapper = queue_mapper
        self.app = None

    def create_app(self):
        app = FastAPI()
        app.add_middleware(  # 添加中间件
            CORSMiddleware,  # CORS中间件类
            allow_origins=["*"],  # 允许起源
            allow_credentials=True,  # 允许凭据
            allow_methods=["*"],  # 允许方法
            allow_headers=["*"],  # 允许头部
        )

        @app.get("/")
        def read_root():
            return {"Hello": "World"}

        @app.get("/v1/models", dependencies=[Depends(check_api_key)])
        async def show_available_models():
            models = [k for k, v in model_config_map.items() if v["enable"]]
            models.sort()
            # TODO: return real model permission details
            model_cards = []
            for m in models:
                model_cards.append(ModelCard(id=m, root=m, permission=[ModelPermission()]))
            return ModelList(data=model_cards)

        @app.post("/api/v1/chat/completions")
        async def create_chat_completion(request: APIChatCompletionRequest):
            """Creates a completion for the chat message"""
            error_check_ret = await check_model(request)
            if error_check_ret is not None:
                return error_check_ret
            error_check_ret = check_requests(request)
            if error_check_ret is not None:
                return error_check_ret

            gen_params = await get_gen_params(
                request.model,
                request.messages,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                echo=False,
                stream=request.stream,
                stop=request.stop,
            )

            if request.repetition_penalty is not None:
                gen_params["repetition_penalty"] = request.repetition_penalty

            error_check_ret = await check_length(
                request, gen_params["prompt"], gen_params["max_new_tokens"]
            )
            if error_check_ret is not None:
                return error_check_ret

            if request.stream:
                generator = chat_completion_stream_generator(
                    request.model, gen_params, request.n
                )
                return StreamingResponse(generator, media_type="text/event-stream")

            choices = []
            chat_completions = []
            for i in range(request.n):
                content = asyncio.create_task(generate_completion(gen_params))
                chat_completions.append(content)
            try:
                all_tasks = await asyncio.gather(*chat_completions)
            except Exception as e:
                return create_error_response(ErrorCode.INTERNAL_ERROR, str(e))
            usage = UsageInfo()
            for i, content in enumerate(all_tasks):
                if content["error_code"] != 0:
                    return create_error_response(content["error_code"], content["text"])
                choices.append(
                    ChatCompletionResponseChoice(
                        index=i,
                        message=ChatMessage(role="assistant", content=content["text"]),
                        finish_reason=content.get("finish_reason", "stop"),
                    )
                )
                task_usage = UsageInfo.parse_obj(content["usage"])
                for usage_key, usage_value in task_usage.dict().items():
                    setattr(usage, usage_key, getattr(usage, usage_key) + usage_value)

            return ChatCompletionResponse(model=request.model, choices=choices, usage=usage)

        @app.post("/generate")
        async def generate(r: typing.Dict):
            try:
                logger.info(r)
                r["method"] = "generate"
                model_name = r.get('model', None)
                texts = r.get('texts', [])
                if len(texts) == 0 or texts is None:
                    return {'code': -1, "msg": "invalid data"}
                if model_name not in model_config_map:
                    msg = "model not in " + ','.join([k for k, v in model_config_map.items() if v["enable"]])
                    print(msg)
                    return {'code': -1, "msg": msg}

                instance = self.queue_mapper[model_name]
                request_id = instance.put(r)
                result = instance.get(request_id)

                return result
            except Exception as e:
                traceback.print_exc()
                print(e)
                return {'code': -1, "msg": str(e)}

        @app.post("/chat")
        async def chat(r: typing.Dict):
            try:
                logger.info(r)
                r["method"] = "chat"
                model_name = r.get('model', None)
                history = r.get('history', [])
                query = r.get('query', "")
                if len(query) == 0 or query is None:
                    return {'code': -1, "msg": "invalid data"}
                if len(history) != 0:
                    assert isinstance(history[0], dict), ValueError('history require dict data')
                    if 'q' not in history[0] or 'a' not in history[0]:
                        raise ValueError('q,a is required in list item')
                if model_name not in model_config_map:
                    msg = "model not in " + ','.join([k for k, v in model_config_map.items() if v["enable"]])
                    print(msg)
                    return {'code': -1, "msg": msg}

                instance = self.queue_mapper[model_name]
                request_id = instance.put(r)
                result = instance.get(request_id)

                return result
            except Exception as e:
                traceback.print_exc()
                print(e)
                return {'code': -1, "msg": str(e)}

        @app.post("/chat_stream")
        def chat_stream(r: typing.Dict):
            try:
                logger.info(r)
                r["method"] = "chat_stream"
                model_name = r.get('model', None)
                history = r.get('history', [])
                query = r.get('query', "")
                n = r.get('n', 4)
                gtype = r.get('gtype', 'total')

                do_sample = r.get('do_sample', True)
                assert do_sample, ValueError("stream not support do_sample=False")
                r['do_sample'] = True
                assert isinstance(n, int) and n > 0, ValueError("require n > 0")
                assert gtype in ['total', 'increace'], ValueError("gtype one of increace , total")

                if len(query) == 0 or query is None:
                    return {'code': -1, "msg": "invalid data"}
                if len(history) != 0:
                    assert isinstance(history[0], dict), ValueError('history require dict data')
                    if 'q' not in history[0] or 'a' not in history[0]:
                        raise ValueError('q,a is required in list item')
                if model_name not in model_config_map:
                    msg = "model not in " + ','.join([k for k, v in model_config_map.items() if v["enable"]])
                    print(msg)
                    return {'code': -1, "msg": msg}

                instance = self.queue_mapper[model_name]
                request_id = instance.put(r)

                def iterdata():
                    while True:
                        result = instance.get(request_id)
                        yield json.dumps(result, ensure_ascii=False)
                        if result["complete"]:
                            break
            except Exception as e:
                traceback.print_exc()
                print(e)

                def iterdata():
                    yield json.dumps({'code': -1, "msg": str(e)}, ensure_ascii=False)

            return StreamingResponse(iterdata(), media_type="application/json")

        return app

    def close_server(self):
        if self.app is not None:
            self.app.stop()

    def run(self):
        self.app = self.create_app()
        uvicorn.run(self.app, host=self.http_ip, port=self.http_port, workers=self.http_num_workers)

