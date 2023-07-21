# -*- coding: utf-8 -*-
# @Author  : ssbuild
# @Time    : 2023/7/21 10:53

from abc import ABC

class Engine_API_Base(ABC):
    def init(self, model_name):
        raise NotImplemented

    def infer(self,input,**kwargs):
        raise NotImplemented