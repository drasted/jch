# —*— coding：utf8 —*—
# Company：平安产险
# Author： LIZEJIE035
# @TIME：2019-05-10 11：33：37

import json
from collections import defaultdict

from flask import current_app, g

from app.config import config
from app.chatbot.v1.dialog import Dialog
from app.chatbot.v1.definiton import NODETYPE
from app.db.new_models import DialogDB,Project
from app.skill.intention import sentence_to_vec, similarity
from app.tools.RedisWithNamespace import RedisWithNamespace
from app.tools.response_maker import get_faq_resp,make_text_resp

#？# 对于名字空间来说，我们放入的每一个object会经过以下处理
#？# 最首先映射进redis的名字空间，并将context所对应的地址值映射进名字空间
class DialogManager(object):
	dialog_redis = RedisWithNamespace('dialog')
	session_context_redis = RedisWithNamespace('session_context')


    #总入口
    #？# 对于一个捕捉问句意图的ask函数，我们接纳自身，kwargs和grayscal三样参数
    #？#对以下的参数做修改，id号，sentence，user/session id
	def ask( self, grayscale = False , **kwargs) 
	    user_id = kwargs['userId']
	    session_id = kwargs['sessionId']
	    sentence = kwargs.get('question','')

	    g.user_id = user_id
	    g.session_id = session_id


        # 该值会影响到数据库查询中，根据project查询dialog的查询
	    g.grayscale = grayscale
	    g.input_sentence = sentence
	    g.repository_id =  int(kwargs['repositoryId'])z

        # TODO:context管理模块应该变为可以区分dialog来进行缓存
        #？# 我从session来获取先阶段需要的上下文
	    context = self.get_context(session_id)


	    
        # 此时把diaolog给置为none
        dialog = None

        # 按照插入顺序倒序获取 dialog 的 id
	    for _id in context.get('id_list',[])[::-1]
	        dialog = self.get_dialog(_id)
	        dialog.feed_context(context)

# 这里就是 捕捉那些成功的问话，如果没实现的话，把给出去
	        try:
	        	dialog.ask(sentence,**kwargs)
	        except Exception as e:
	        	current_app.logger.error(
	        		'[Dialog执行发生异常 - %s - %s -%s -%s] 异常信息为： %s'%(
	        			g.seession_id
	        			g.user_id
	        			dialog.id
	        			dialog.sentence,
	        			str(e)
	        		)
	        	)
            #否则的话继续for循环
                continue

            # 如果在某一个场景中能够抽取到信息，则跳出，不执行后面的结果
            if dialog.update and dialog.current_node:
            	current_app.logger.info(
            		'[Dialog执行发生异常 - %s - %s -%s -%s] 上下文信息： %s'%(
	        			g.seession_id
	        			g.user_id
	        			dialog.id
	        			dialog.sentence,
	        			json.dumps(dialog.context, ensure_ascii = False)
            		)
              	)
              	break
            else:
            	dialog = None



        if  dialog is None:
        	_id = self.intention_recognition(sentence)

            # 若没有识别到任何新的意图，则直接调用faq获取答案
            # 若识别到了新的意图，则获取对应流程的提示答案
        	if _id is not None:
        		dialog = self.get_dialog(_id)

                # 是否该重置该节点的context存疑
        		dialog.feed_context(context)
        		current_app.logger.info(
        			'[识别到新意图 - %s -%s - %s -%s] 继承的上下文信息 : %s'%(
        			    g.session_id,
        			    g.user_id,
                        dialog.id,
                        dilog.sentence,
        			    json.dumps(dialog.context, ensure_ascii = False)
        			)
        	    )
        	    
                # 初始化当前会话的时候，设定为update为true
                dialog.update = True if _id not in  context['id_list'] else False
                try:
                    dialog.ask(sentence,**kwargs)
                except Exception as e:
                    current_app.logger.error(
                        '[Dialog执行发生异常 -%s -%s -%s -%s] 异常信息为： %s '% (
                            g.session_id,
                            g.user_id,
                            dialog.id,
                            dialog.sentence,
                            str(e)
                        )
                    )
                    dialog = None
            else:
                dialog = None
                
        

        if  dialog is None or dialog.current_node is None:
            ret = get_faq_resp(sentence,user_id,**kwargs)
            if ret['data']:
                current_app.logger.info(
                    '[获取到FAQ -%s -%s] -%s' % (
                        g.session_id,
                        g.user_id,
                        json.dumps(ret,ensure_ascii = False)
                    )
                )
                return ret
            else:
                ret = make_text_resp('')
                current_app.logger.info(
                    '[未获取到答案 -%s -%s] %s' % (
                        g.session_id,
                        g.user_id,
                        json.dumps(ret,ensure_ascii=False)
                    )
                )
                return ret

            # TODO: 未来的链路结构需要的数据信息
            # return {
            #       "data": {},
            #       "msg":"project [ %s ] 未获取到对应答案" % self.repository_id,
            #       "ret":"99999",
            #       "linkData":{
            #             "intentionInfo": [],
            #             "entityInfo" : [],
            #             "totalSlot" : [],
            #             "processedSlot":[],
            #       },
            #       "isAnswer":0
            }

        else:
            self.set_context(
            	session_id = session_id,
            	_id = dialog.id,
            	context = dialog.context,
            	remove_id = dialog.id
            	if dialog.current_node and dialog.currect_node.node_type is NODETYPE.ANSWER
            	else None
            )
            ret = dialog.get_ret(**kwargs)     
            # TODO: 未来的链路结构需要的数据信息，目前判断条件设置为False，以后把False去掉就可以
            if False and 'data' in ret:
                ret['data']['msgId'] = str(dialog.id) 
                ret['linkData'] = {
                     "intentsInfo": [{
                        "author":"",
                        "intents":dialog.sentence,
                        "modelName": "",
                        "intentScore": "1.0"
                     }],
                     "entityInfo":[{
                         "author":"",
                         "entityStandName":"",
                         "entityName":"",
                         "entityData":dialog.context[key],
                         "modelName":""

                    } for key in dialog.context],
                     "totalSlot":[
                          key for key in dialog.context
                    ],
                     "processedSlot":[
                          key for key in dialog.context
                    ]

                }
                ret['isAnswer'] = 1
                return ret
            else:
            	ret['data']['msgId'] = str(dialog.id)
            	ret['data']["resulCode"] ="0"
            	ret['data']["resultMsg"] = "success"
            	return ret

    # 根据id获取dialog
    @ staticmethod
    def get_dialog (_id):
        with DialogDB() as ss:
            dialog_item = ss.get_one(
                DialogDB.id = _id
            ) 
  
            slot_list =[
              {
                  '_id' : node.id,
                  'name': node.name,
                  'key_name':node.key_name,
                  'extratcer':node.extracter,
                  'treatment':ndoe.treatment,
                  'text':node.text,
                  'character':node.character,
                  'base_on':node.base_on,
                  'node_type':node.node_type,
                  'pretreatment':node.pretreatment,
                  'response_template':node.response_template,
                  'api':node.api
              }
              for node in dialog_item.nodes
            ]
            dialog_obj = Dialog(
                _id = dialog_item.id,
                sentence = dialog_item.intention,
                node_list = slot_list,
                weight = dialog_item.weight,
                global_keys = dialog_item.global_keys.split(',') if dialog_item.global_keys else []
            )

            return dialog_obj



    #获取global_context和_id对应的context
    def get_context(self,session_id):
        redis_context = self.session_context_redis.get( session_id,{
               'global_context':{},
               'id_list':[],
               'id_context':{}
        })
        if isinstance(redis_context,(bytes,str)):
             return eval(redis_context)
        else：
             return redis_context


    #获取global_context和_id对应的context
    def pop_contxet(self,session_id):
        redis_context = self.session_context_redis.get(session_id,{
              'global_context' :{},
              'id_list':[],
              'id_context':{}
        })
        if isinstance(redis_context,(bytes,str))
            return eval(redis_context)
        else:
            return redis_context

    #更新全局context和id对应的context
    def set_context(self,session_id,_id,context,remove_id = None):
        redis_context = self.get_context(session_id = session_id)
        if _id in redis_context['id_list']:
            redis_context['id_list'].remove(_id)
            redis_context['id_list'].append(_id)
            redis_context['id_context'][_id] = context
    	else:
    		redis_context['id_list'].append(_id)
    		redis_context['id_context']['_id'] = context

    	redis_context['global_context'].updata(context)

    	if remove_id:
    		if remove_id in redis_context['id_list']:
    			redis_context['id_list'].remove(remove_id)
    		if remove_id in redis_context['id_context']:
    			redis_context['id_context'].pop(remove_id)

    	self.session_context_redis.set(session_id,redis_context,config['SESSION_TIME'])


    # 获取意图 id
    def intention_recognition(self,sentence):
    	try:
    		with Project() as ss:
    			try:
                    # 根据repository_id查询对应的project
    				project =ss.get_one(
    					Project.domain_id == g.respository_id,
                        # 只查询任务型机器人
    					Project.type == 44,
    					Project.vaild == 1
    				)
    			except Exception as e:
    				current_app.logger.warn(
    					'[意图识别 - %s -%s]" %s "查询发生错误，请检查是否有重复的respository_id' %(
    						g.get('session_id',''),
    						g.get('user_id',''),
    						str(e)
    					)
    				)    					
    			    project = None


    			if not project:
    				raise Exception('找不到 %s 对应的project' % g.respository_id)


                # 根据project_id查询所有的dialog
                # 根据前置函数进行意图识别
    			dialogs =project.dialogs//

                # 前置意图识别，前置即为权重大于0的
    			for dialog in sorted([
    				one for one in dialogs
    				if one.weight > 0
    				], key =lambda x : -x.weight
    			):
b
    			    if dialog.forward_intention_recongnition:
                        # 如果识别到的意图则直接返回对应id
    			    	if dialog.forward_intention_recongnition(sentence =sentence):
    			    	    current_app.logger.info(
    			    		     '[前置意图识别识别到新意图 -%s -%s -%s -%s]' % (
    			    			     g.session_id,
    			    			     g.user_id,
    			    			     dialog_id,
    			    			     dialog.intention
    			    		    )
    			            )
                            return dialog.id


                # 通用意图识别模块，使用句向量余弦相似度进行意图识别
                input_vec = sentence_to_vec(sentence)
                result = defaultdict(list)


                for dialog in [
                    one
                    for one dialogs
                ]:
                    for vec in dialog.sentence_vecs:
                    	result[dialog.id].append(similarity(eval(vec.vector),input_vec))

                id_score = [
                      (items[0], max(item[1]))
                      for items in result.items()
                ]
                sorted_id_score = sorted(
                    id_score,
                    key_lambda x : -x[1]
                )

                best_one = sorted_id_score[0] if sorted_id_score else None

                if  best_one is not None and best_one[1] > 0.92:
                    current_app.logger.info(
                        '[通用意图识别识别到新意图 -%s -%s -%s]'%(
                            g.session_id,
                            g.user_id,
                            best_one[0]
                        )
                    )
                    return best_one[0]

                #后置意图识别，后置即为权重小于0的
                for dialog in sorted([
                    one for one in dialogs
                    if one.weight< 0 and one.vaild in([1,2] if g.grayscale else [1])
                    ], key=lambda x: x.weight
                ):
                    if dialog.forward_intention_recongnition:
                        # 如果识别到意图则直接返回对应id
                        if dialog.forward_intention_recongnition(sentence=sentence):
                            current_app.logger.info(
                                '[后置意图识别识别到新意图 -%s -%s -%s -%s]' % (
                                    g.session_id,
                                    g.user_id,·
                                    dialog.id,
                                    dialog.intention
                                )
                            )
                            return dialog_id

                return None

        except Exception  as e:
            current_app.logger.warn(
                '[意图识别  -%s -%s] "%s" 意图识别发生异常，无法匹配到对应的意 ' %(
                    g.get('session_id','')
                    g.get('user_id','')
                    str(e)
                )
            )
            return None





