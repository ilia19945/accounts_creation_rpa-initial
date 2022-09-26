import json
import os
import re
import time
from pprint import pprint

from funcs import send_jira_comment, notion_search_for_role, notion_search_for_permission_block_children, get_notion_page_title, compare_permissions_by_name, compare_role_configs_google, full_compare_by_name_and_permissions_with_file, fetching_params_from_file, checking_config_for_service_existence

# \ compare_permissions

jira_key = "AUS2-25"
position_title = "User Support Engineer"
# position_title = "Chief People Officer"

# работает, для теста отключил
# permissions_for_persona_list = notion_search_for_role(position_title, jira_key=jira_key)  # the list of page_ids

permissions_for_persona_list = [{'id': 'bc107629-7902-4e25-b9b3-78f60bade8fa'},
                                {'id': '87168944-82fd-4457-a4ac-42d06ad9edf7'},
                                {'id': 'ec8dd479-fefe-4c1a-b219-15e8d1687a53'},
                                {'id': '909640d5-58d7-40ab-9318-c30617ef3cae'},
                                {'id': 'eda65b3b-7e2e-4810-b024-e6bfb64bfe26'},
                                {'id': 'b7dd8b19-6615-4c68-9c5c-7d51a840ed12'},
                                {'id': '28dbe973-dbd1-4967-9371-96df3b04abf7'},
                                {'id': '96e4ee54-2e86-496f-a80e-331a0c31cb96'},
                                {'id': 'f34b5830-82f8-420f-ad01-b73c0d208b88'},
                                {'id': 'e28ef474-bd2b-4d6f-b6c5-8375ee0f02a3'},
                                {'id': 'a0d6618a-5f3c-49fb-a02e-1ce415bfc218'},
                                {'id': 'e0ad92ca-1ddc-4ebe-a7e0-194b56bad13a'},
                                {'id': '7d062dba-6243-42b3-82b0-57437a669d99'},
                                {'id': '21fa797b-0d50-46f0-88e8-ca701869b316'},
                                {'id': 'b5eed21c-a5cc-463e-ae24-30a9324afd3e'},
                                {'id': 'af69bf7e-d041-4387-a8dd-0ecee3e75d44'},
                                {'id': '303531cf-d987-4380-9eb9-b468a62223f7'},
                                {'id': '0cf421dc-495f-45a3-9d8e-908ecb1c6a60'},
                                {'id': 'fe402216-2206-41ce-9f54-3e5baf1e1aa6'},
                                [[{'id': '1b90d87e-7304-4774-8bef-8a5e41b1c4e8'},
                                  {'id': '3d011a6c-989f-439a-b0df-bffda5f0bcd7'}]],
                                [[{'id': '79b58639-8850-44d7-8d29-46a437345931'},
                                  {'id': 'ab2b7a8b-0618-4e53-b762-026d277d9e0a'}]],
                                [[{'id': '85fe26e7-8c05-468c-aa7b-c62407bc243d'},
                                  {'id': '0f0c8768-fb86-4812-a942-f49005ac2478'}]]]

"""if len(permissions_for_persona_list) == 0:
    print(f'Permissions are not added for {position_title}!')
    # send_jira_comment(f'Permissions are not added for *{position_title}* position ❌', jira_key=jira_key)
    # return  # ⚠️ ⚠️ ⚠️stops the main flow!
else:

    # trying to create a directory for this role:
    # path = os.path.join(f".\\roles_configs\\{jira_key}", position_title)
    # mode = 0o666
    # os.makedirs(path, mode)

    pages_list = ''
    for i in range(len(permissions_for_persona_list))[::-1]:  # как было раньше

        # print(type(permissions_for_persona_list[i]))
        # print(permissions_for_persona_list[i-1])
        # print(type(permissions_for_persona_list[i-1]))
        # print()
        # print()

        current_permissions_set = permissions_for_persona_list[i]
        antecedent_permissions_set = permissions_for_persona_list[i - 1]

        # здесь текущий (n) и за ним уровень (n-1) - НЕ корневые
        if type(current_permissions_set) == list and type(antecedent_permissions_set) == list:  # здесь имеем сет из пермиссий, каждый из которых нужно сравнить с предыдущим, с конца*
            # print(f"{permissions_for_persona_list[i]} --- {type(*permissions_for_persona_list[i])}, this is a nested permissions")
            # print(current_permissions_set[0])
            # print(antecedent_permissions_set[0])
            print("текущий и предыдущий сет пермиссий - листы")
            print()

            for p in range(len(current_permissions_set[0])):  # берем n уровень, проверяем каждую пермиссию
                current_permission_id = current_permissions_set[0][p]['id']
                current_role_name = get_notion_page_title(current_permission_id).json()['properties']['Name']['title'][0]['plain_text']
                current_role_url = get_notion_page_title(current_permission_id).json()['url']

                print('current_role_name:', current_role_name)
                print('current_role_url:', current_role_url)
                print('current_permission_id:', current_permission_id)

                # try:
                current_result = notion_search_for_permission_block_children(current_permission_id)  # запрашиваем есть ли json
                print('got out of notion_search_for_permission_block_children')

                # тут - значит что все ок, json в пермиссии - валидный
                if type(current_result) == tuple:  # because the correct option should contain "True" i.e. - (result,True)
                    # pages_list += f"[{current_role_name}|{current_role_url}]: Validated, Good Job! ✅ \n"

                    pages_list += f"{current_role_name}: Validated, Good Job! ✅ \n"
                    print(f"{current_role_name}: Validated, Good Job! ✅ \n")

                    # проверим, а к какой роли относится этот json?

                    if re.findall('googleworkspace', current_role_name):  # содержит googleworkspace
                        print('checking permissions on antecedent role')
                        for r in range(len(antecedent_permissions_set[0])):  # берем каждую пермиссию из n-1 уровня

                            antecedent_permission_id = antecedent_permissions_set[0][r]['id']
                            antecedent_role_name = get_notion_page_title(antecedent_permission_id).json()['properties']['Name']['title'][0]['plain_text']
                            antecedent_role_url = get_notion_page_title(antecedent_permission_id).json()['url']

                            print(f'antecedent_role_name: "{antecedent_role_name}"')
                            print(f'antecedent_role_url: "{antecedent_role_url}"')
                            print(f'antecedent_permission_id: "{antecedent_permission_id}"')
                            print('')

                            if re.findall('googleworkspace', antecedent_role_name):
                                try:
                                    antecedent_result = notion_search_for_permission_block_children(antecedent_permission_id)  # запрашиваем есть ли json
                                    print("antecedent_result:")
                                    print(type(antecedent_result))
                                    print("XXXXXXXXXXXXXXXXXXXXXXXX")

                                    if type(antecedent_result) == tuple:  # because the correct option should contain "True" i.e. - (result,True)
                                        # pages_list += f"---- [{antecedent_role_name}|{antecedent_role_url}]: Validated, Good Job! ✅ \n"
                                        pages_list += f"---- [{antecedent_role_name}|]: Validated, Good Job! ✅ \n"
                                        print('testestestest1')

                                    else:
                                        print('testestestest2')
                                        # pages_list += f"---- [{antecedent_role_name}|{antecedent_role_url}]: {antecedent_result}\n"
                                        pages_list += f"---- [{antecedent_role_name}|]: {antecedent_result}\n"

                                except Exception as e:

                                    print("antecedent_result_exception:")
                                    print(current_role_name, " - ", current_result)
                                    print(e)

                            else:
                                print('googleworkspace is not found in antecedent_role_permissions')
                            print('---------------current iter end---------------')





                    elif re.findall('amazonconnect', current_role_name):
                        print('amazonconnect')
                    elif re.findall('juneos', current_role_name):
                        print('juneos')
                    elif re.findall('frontapp', current_role_name):
                        print('frontapp')
                    elif re.findall('slack', current_role_name):
                        print('slack', current_role_name)
                    else:
                        print('else:', current_role_name)
                        pass

                # тут - значит что json невалидный в текущей пермиссии
                else:
                    print(current_role_name, " - ", current_result)
                    print()
                    pages_list += f"[{current_role_name}|{current_role_url}]: {current_result}\n"
                    # pass

                # except Exception as e:
                #     print(e)

            # в цикле пройтись по каждой пермиисии и сравнить ее с i-1 тоже каждой пермиссией, и найти матчи,
                # каждый матч проверить и обновить

        # здесь текущий лист, а за ним уже корневые пермиссии
        elif type(current_permissions_set) == list:
            print("только текущий - лист, предыдущий - str")

            # ок работает
            # for j in range(len(roles)):
            #     # print('role:', roles[j])
            #     role_name = get_notion_page_title(roles[j]['id']).json()['properties']['Name']['title'][0]['plain_text']
            #     role_url = get_notion_page_title(roles[j]['id']).json()['url']
            #     # print(role_name)
            #     # print(role_url)
            #     try:
            #         result = notion_search_for_permission_block_children(roles[j]['id'])
            #
            #         if type(result) == tuple:  # because the correct variant should contain "True" i.e. - (result,True)
            #             pages_list += f"[{role_name}|{role_url}]: Validated, Good Job! ✅ \n"
            #
            #         else:
            #             pages_list += f"[{role_name}|{role_url}]: {result}\n"
            #     except Exception as e:
            #         print(e)
            # print('---')

        else:  # здесь обычные пермиссии
            # print(f"{permissions_for_persona_list[i]} --- {type(permissions_for_persona_list[i])}, this is a regular normal permission")
            # print("обычная пермиссия")
            pass

    print(pages_list)"""
#
#    # for i in range(len(permissions_for_persona_list)): # как было раньше
#    # for i in range(2, -1, -1):
#    #     role_name = get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']
#    #     role_url = get_notion_page_title(permissions_for_persona_list[i]['id']).json()['url']
#    #     print(f"Reviewing {i + 1} / {len(permissions_for_persona_list)} permissions...for ({role_name})")
#    #     try:
#    #         result = notion_search_for_permission_block_children(permissions_for_persona_list[i]['id'])
#    #
#    #         if type(result) == tuple:  # because the correct variant should contain "True" i.e. - (result,True)
#    #             pages_list += f"[{role_name}|{role_url}]: Validated, Good Job! ✅ \n"
#    #
#    #             with open(f".\\roles_configs\\{jira_key}\\{position_title}\\{role_name}.json", 'w+') as file:
#    #                 file.write(str(json.dumps(result[0])))
#    #         else:
#    #             pages_list += f"[{role_name}|{role_url}]: {result}\n"
#    #     except Exception as e:
#    #         print(e)
#    # print(pages_list)
#    # send_jira_comment(message=f"The summary after reviewing permissions for {position_title} persona:\n{pages_list}", jira_key=jira_key)


if len(permissions_for_persona_list) == 0:
    print(f'Permissions are not added for {position_title}!')
    # send_jira_comment(f'Permissions are not added for *{position_title}* position ❌', jira_key=jira_key)
    # return  # ⚠️ ⚠️ ⚠️stops the main flow!
else:

    # # trying to create a directory for this role:
    # path = os.path.join(f".\\roles_configs\\{jira_key}", position_title)
    # mode = 0o666
    # os.makedirs(path, mode)

    pages_list = ''
    for i in range(len(permissions_for_persona_list))[::-1]:  # как было раньше

        # print(type(permissions_for_persona_list[i]))
        # print(permissions_for_persona_list[i-1])
        # print(type(permissions_for_persona_list[i-1]))
        # print()
        # print()

        current_permissions_set = permissions_for_persona_list[i]
        antecedent_permissions_set = permissions_for_persona_list[i - 1]

        # здесь текущий (n) и за ним уровень (n-1) - НЕ корневые |||| ✅ - все работает, закомменчено для скорости
        # пока только для гугла, потом написать конфиги для остальных сервисов
        if type(current_permissions_set) == list and type(antecedent_permissions_set) == list:  # здесь имеем сет из пермиссий, каждый из которых нужно сравнить с предыдущим, с конца*
            # # print(f"{permissions_for_persona_list[i]} --- {type(*permissions_for_persona_list[i])}, this is a nested permissions")
            # # print(current_permissions_set[0])
            # # print(antecedent_permissions_set[0])
            print("текущий и предыдущий сет пермиссий - листы")

            for p in range(len(current_permissions_set[0])):  # берем n уровень, проверяем каждую пермиссию
                # получаем результат проверки для коммента, название текущей роли и json конфиг
                pages_list, current_role_name, current_json_object = compare_permissions_by_name(permissions_set=current_permissions_set,
                                                                                                 pages_list=pages_list,
                                                                                                 iterator=p,
                                                                                                 level=1)

                if not current_json_object:  # failed or missing json_config should not be added to config
                    print('there is an error in the document', current_json_object)
                    pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"

                else:
                    print('current_json_object:')
                    pprint(current_json_object, indent=1)

                    if re.findall('googleworkspace', current_role_name):

                        relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                            config_name='googleworkspace',
                            antecedent_permissions_set=antecedent_permissions_set,
                            jira_key=jira_key,
                            position_title=position_title,
                            current_json_object=current_json_object,
                            pages_list=pages_list,
                            current_role_name=current_role_name)

                    elif re.findall('amazonconnect', current_role_name):

                        relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                            config_name='amazonconnect',
                            antecedent_permissions_set=antecedent_permissions_set,
                            jira_key=jira_key,
                            position_title=position_title,
                            current_json_object=current_json_object,
                            pages_list=pages_list,
                            current_role_name=current_role_name)

                    elif re.findall('juneos', current_role_name):

                        relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                            config_name='juneos',
                            antecedent_permissions_set=antecedent_permissions_set,
                            jira_key=jira_key,
                            position_title=position_title,
                            current_json_object=current_json_object,
                            pages_list=pages_list,
                            current_role_name=current_role_name)
                    elif re.findall('frontapp', current_role_name):

                        relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                            config_name='frontapp',
                            antecedent_permissions_set=antecedent_permissions_set,
                            jira_key=jira_key,
                            position_title=position_title,
                            current_json_object=current_json_object,
                            pages_list=pages_list,
                            current_role_name=current_role_name)

                    elif re.findall('slack', current_role_name):

                        relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                            config_name='slack',
                            antecedent_permissions_set=antecedent_permissions_set,
                            jira_key=jira_key,
                            position_title=position_title,
                            current_json_object=current_json_object,
                            pages_list=pages_list,
                            current_role_name=current_role_name)

                    else:
                        print('else:', current_role_name)
                        pass
                # print('-----end-iter-----')
            pass

        # здесь текущий лист, а за ним уже корневые пермиссии
        elif type(current_permissions_set) == list and type(antecedent_permissions_set) == dict:
            # print("только текущий - лист, предыдущий - str")

            pages_list += '\n'
            print(f"{current_permissions_set} --- {type(current_permissions_set)}, current_permissions_set")
            print(f"{antecedent_permissions_set} --- {type(antecedent_permissions_set)}, antecedent_permissions_set")

            items_list = []

            try:
                items_list = checking_config_for_service_existence(
                    role_title=position_title,
                    jira_key=jira_key,
                )

            except Exception as e:
                print(f"Error occurred on: {e}")
            print(items_list)

            for p in range(len(current_permissions_set[0])):  # берем n уровень, проверяем каждую пермиссию

                current_permission_id = current_permissions_set[0][p]['id']
                current_role_name = get_notion_page_title(current_permission_id).json()['properties']['Name']['title'][0]['plain_text']
                current_role_url = get_notion_page_title(current_permission_id).json()['url']

                # print()
                # print()
                # print('current_role_name:', current_role_name)
                # print('current_role_url:', current_role_url)
                # print('current_permission_id:', current_permission_id)
                # print()
                # print()

                current_result = notion_search_for_permission_block_children(current_permission_id)  # запрашиваем есть ли json
                print('current_result:', current_result)
                # print('got OUT of notion_search_for_permission_block_children')
                if type(current_result) == tuple:
                    for i in range(len(items_list)):
                        config_name = re.split('_', items_list[i])[0]
                        # print("name -", config_name, ", current_role_name -", current_role_name)
                        if re.findall(config_name, current_role_name):
                            print("name -", config_name, ", current_role_name -", current_role_name)
                            filename = f".\\roles_configs\\{jira_key}\\{position_title}\\{config_name}_config.json"
                            print('trying to read: ')
                            try:
                                with open(filename, 'r') as file:
                                    data = json.loads(file.read())
                                    print("data:", data)
                            except Exception as e:
                                print(e)

                            else:
                                if config_name == 'googleworkspace':
                                    relevant_config = compare_role_configs_google(current_result[0], data)
                                    print(relevant_config)
                                    with open(filename, 'w+') as file:
                                        json.dump(relevant_config, file, indent=4)

                                elif config_name == 'slack':
                                    relevant_config = compare_role_configs_google(current_result[0], data)
                                    print(relevant_config)
                                    with open(filename, 'w+') as file:
                                        json.dump(relevant_config, file, indent=4)

                                elif config_name == 'amazonconnect':
                                    relevant_config = compare_role_configs_google(current_result[0], data)
                                    print(relevant_config)
                                    with open(filename, 'w+') as file:
                                        json.dump(relevant_config, file, indent=4)


                    pages_list += f"*[{current_role_name}|{current_role_url}]* : Validated. ✅\n"

                else:
                    pages_list += f"*[{current_role_name}|{current_role_url}]*: {current_result}\n"
                    pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"


            # print('current_result')
            # print(current_result)
            # print('==============')

            pass

            # ок работает
            # for j in range(len(roles)):
            #     # print('role:', roles[j])
            #     role_name = get_notion_page_title(roles[j]['id']).json()['properties']['Name']['title'][0]['plain_text']
            #     role_url = get_notion_page_title(roles[j]['id']).json()['url']
            #     # print(role_name)
            #     # print(role_url)
            #     try:
            #         result = notion_search_for_permission_block_children(roles[j]['id'])
            #
            #         if type(result) == tuple:  # because the correct variant should contain "True" i.e. - (result,True)
            #             pages_list += f"[{role_name}|{role_url}]: Validated, Good Job! ✅ \n"
            #
            #         else:
            #             pages_list += f"[{role_name}|{role_url}]: {result}\n"
            #     except Exception as e:
            #         print(e)
            # print('---')

        # здесь обычные пермиссии
        else:
            # print(f"{permissions_for_persona_list[i]} --- {type(permissions_for_persona_list[i])}, this is a regular normal permission")
            # print("обычная пермиссия")
            pass

    print()
    print(pages_list)
    send_jira_comment(message=f"Summary after reviewing permissions for *{position_title}* persona:\n{pages_list}", jira_key=jira_key)
