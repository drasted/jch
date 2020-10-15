# -*- coding:utf-8 -*- #

import requests
import config
import json
from app import logger
from app import cache
from flask import current_app


def billing_deal_func(data,results,scene_list,lable,prob):
	# 出单入口
	# TODO 0
	keyValue = data['userId'] + "_" + data['sessionId']
	UserInfo = cache.get(keyValue)
	userInfo = UserInfo[data['userId']][data['sessionId']]

	userInfo["billingStatus"] = "1"

	if scene_list.get(lable,"") == "30028" and prob>0.975 and userInfo.get("OrderId") !="30028" #我要出单场景
		# noinspection PyBoardException
		try:
			#开始出单流程
			if scene_list.get(lable,"") == "30028" and userInfo.get("orderid") != "30028":
				if userInfo.get("billingStatus","") == "1": #是否报价权限
					results["content"] = {"answer":"","instrcution":"101","intention_id":"30028",
											"oral_contant":{task_id:"145"}}
					results["status"] = {"msg":"success","state":"1"}
					userInfo["orderid"] = "30028"
				else:
					results["content"] = {"answer":"您的账号暂时不支持语音出单，您可以在车险投保模块里面出单"}
										"oral_contant"：{"task_id":"145"}}
					results["status"] = {"msg":"success","state":"1"}
				
				cache.set( keyValue,UserInfo, timeout = current_app.config['TINEOUT'])
				return results
		except Exception as e:
			logger.error(e)
			pass


	elif scene_list.get(lable,"") == "30028" or data.get("questionType","") == "46" or data.get("questio","")\
			and userInfo.get("orderid") == "30028": # 进入出单流程下的子流程
		#TODO
		header = {"Content-Type":"application/json"}
		if data.get{"billingInputData",""}
			exp_chat_proxy_url = "http://10.118.146.244:8095/ai/partner/chat" # 开发
			dev_chat_proxy_url = "http://30.79.75.80:80/ai/partner/chat" # 测试
			prob_chat_proxy_url = "http://30.4.132.46:8080/pingan/passth/partnerChat" #生产

			proxy_input = {}
			proxy_input.updata(data["billingInputData"])

			if config.DB_MORE == "PRO":
				intent_data = requests.post(prob_chat_proxy_url,
											data = json.dumps(proxy_input)，
											header = header)
				proxy_output = json.loads(intent_data.text)
			elif config.DB_MORE == "TEST":
				intent_data = requests.post(dev_chat_proxy_url,
											data = json.dumps(proxy_input),
											headers = header)
				proxy_output = json.loads(intent_data.text)
			else:
				intent_data = requests.post(exp_chat_proxy_url,
											data = json.dumps(proxy_input),
											headers = header )
				proxy_output = json.loads(intent_data.text)

			results["orderBackData"] = proxy_output
			results["content"]["answer"] = ""
			results["status"] = {"msg":"success","state":"1"}

			if proxy_output.get ("endFlag","") == "Y":
				#TODO
				userInfo["orderid"] = ""
				cache.set( keyValue, UserInfo, timeout = current_app.config["TIMEOUT"])

			return results

	else:
		return None