import json
import os
import re
import time
from pprint import pprint

from funcs import send_jira_comment, notion_search_for_role, notion_search_for_permission_block_children, get_notion_page_title, compare_permissions_by_name, compare_role_configs_google, full_compare_by_name_and_permissions_with_file, fetching_params_from_file, checking_config_for_service_existence, \
comparing_permission_from_notion_vs_config_on_disk

# \ compare_permissions

jira_key = "AUS2-25"
position_title = "User Support Engineer"
# position_title = "Chief People Officer"

permissions_history_check = []

# работает, для теста отключил
permissions_for_persona_list = notion_search_for_role(position_title, jira_key=jira_key)  # the list of page_ids
#
# pprint(permissions_for_persona_list)
# raise Exception
# permissions_for_persona_list = [{'id': 'bc107629-7902-4e25-b9b3-78f60bade8fa'},
#                                 {'id': '87168944-82fd-4457-a4ac-42d06ad9edf7'},
#                                 {'id': 'ec8dd479-fefe-4c1a-b219-15e8d1687a53'},
#                                 {'id': '909640d5-58d7-40ab-9318-c30617ef3cae'},
#                                 {'id': 'eda65b3b-7e2e-4810-b024-e6bfb64bfe26'},
#                                 {'id': 'b7dd8b19-6615-4c68-9c5c-7d51a840ed12'},
#                                 {'id': '28dbe973-dbd1-4967-9371-96df3b04abf7'},
#                                 {'id': '96e4ee54-2e86-496f-a80e-331a0c31cb96'},
#                                 {'id': 'f34b5830-82f8-420f-ad01-b73c0d208b88'},
#                                 {'id': 'e28ef474-bd2b-4d6f-b6c5-8375ee0f02a3'},
#                                 {'id': 'a0d6618a-5f3c-49fb-a02e-1ce415bfc218'},
#                                 {'id': 'e0ad92ca-1ddc-4ebe-a7e0-194b56bad13a'},
#                                 {'id': '7d062dba-6243-42b3-82b0-57437a669d99'},
#                                 {'id': '21fa797b-0d50-46f0-88e8-ca701869b316'},
#                                 {'id': 'b5eed21c-a5cc-463e-ae24-30a9324afd3e'},
#                                 {'id': 'af69bf7e-d041-4387-a8dd-0ecee3e75d44'},
#                                 {'id': '303531cf-d987-4380-9eb9-b468a62223f7'},
#                                 {'id': '0cf421dc-495f-45a3-9d8e-908ecb1c6a60'},
#                                 {'id': 'fe402216-2206-41ce-9f54-3e5baf1e1aa6'},
#                                 [
#                                     [{'id': '1b90d87e-7304-4774-8bef-8a5e41b1c4e8'},
#                                      {'id': '3d011a6c-989f-439a-b0df-bffda5f0bcd7'}]
#                                 ],
#                                 [
#                                     [{'id': '79b58639-8850-44d7-8d29-46a437345931'},
#                                      {'id': 'ab2b7a8b-0618-4e53-b762-026d277d9e0a'}]
#                                 ],
#                                 [
#                                     [{'id': '85fe26e7-8c05-468c-aa7b-c62407bc243d'},
#                                      {'id': '0f0c8768-fb86-4812-a942-f49005ac2478'}]
#                                 ]
#                                 ]


# permissions_for_persona_list = [{'id': 'bc107629-7902-4e25-b9b3-78f60bade8fa'},
#                                 {'id': 'b7dd8b19-6615-4c68-9c5c-7d51a840ed12'},
#                                 {'id': '96e4ee54-2e86-496f-a80e-331a0c31cb96'},
#                                 {'id': 'ec8dd479-fefe-4c1a-b219-15e8d1687a53'},
#                                 {'id': '87168944-82fd-4457-a4ac-42d06ad9edf7'},
#                                 {'id': '909640d5-58d7-40ab-9318-c30617ef3cae'},
#                                 {'id': '7d062dba-6243-42b3-82b0-57437a669d99'},
#                                 {'id': 'b5eed21c-a5cc-463e-ae24-30a9324afd3e'},
#                                 {'id': 'af69bf7e-d041-4387-a8dd-0ecee3e75d44'},
#                                 {'id': '303531cf-d987-4380-9eb9-b468a62223f7'},
#                                 [[{'id': '3d011a6c-989f-439a-b0df-bffda5f0bcd7'},
#                                   {'id': '1b90d87e-7304-4774-8bef-8a5e41b1c4e8'}]],
#                                 [[{'id': '79b58639-8850-44d7-8d29-46a437345931'},
#                                   {'id': 'ab2b7a8b-0618-4e53-b762-026d277d9e0a'}]],
#                                 [[{'id': '0f0c8768-fb86-4812-a942-f49005ac2478'},
#                                   {'id': '85fe26e7-8c05-468c-aa7b-c62407bc243d'}]]]

if len(permissions_for_persona_list) == 0:  # если пермиссии для персоны не добавлены!
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
            print("current and previous permissions sets are both type 'List'")

            # ================================================
            # ВСЕ РАБОТАЕТ УРА!!! ПРОСТО РАСКОММЕНТИТЬ ТО ЧТО МЕЖДУ ===
            #
            for p in range(len(current_permissions_set[0])):  # берем n уровень, проверяем каждую пермиссию
                # получаем результат проверки для коммента, название текущей роли и json конфиг
                pages_list, current_role_name, current_json_object = compare_permissions_by_name(permissions_set=current_permissions_set,
                                                                                                 pages_list=pages_list,
                                                                                                 iterator=p,
                                                                                                 level=1,
                                                                                                 jira_key=jira_key,
                                                                                                 position_title=position_title)

                if not current_json_object:  # failed or missing json_config, should not be added to config
                    print('there is an error in the document', current_json_object)
                    pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"

                else:
                    print(f'current_json_object for "{current_role_name}":')
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
                        relevant_config = False
                        pass
                # print('-----end-iter-----')
            # ================================================
            pass

        # здесь текущий лист, а за ним уже корневые пермиссии
        elif type(current_permissions_set) == list and type(antecedent_permissions_set) == dict:
            print("current  permissions set is 'list' while the previous permissions set is 'dict'")
            pass

            # ================================================
            # ВСЕ РАБОТАЕТ УРА!!! ПРОСТО РАСКОММЕНТИТЬ ТО ЧТО МЕЖДУ ===
            #
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

                print('current_role_name:', current_role_name)
                # print('current_role_url:', current_role_url)
                # print('current_permission_id:', current_permission_id)

                current_result = notion_search_for_permission_block_children(current_permission_id)  # запрашиваем есть ли json
                print('current_result type:', type(current_result))
                print('current_result:', current_result)
                # print('got OUT of notion_search_for_permission_block_children')

                if type(current_result) == tuple:
                    # print(data)
                    # if data != 'False':
                    print('data in the config != false')
                    for i in range(len(items_list)):
                        config_name = re.split('_', items_list[i])[0]
                        print("config_name -", config_name, ", current_role_name -", current_role_name)
                        if re.findall(config_name, current_role_name):
                            print('permissions can be compared')
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
                                    print()
                                    print('======== this is relevant config')
                                    print(relevant_config)
                                    print('========')
                                    print()
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
                        else:
                            print('^incomparable permissions, skipping')
                            print('------------')

                    pages_list += f"*[{current_role_name}|{current_role_url}]* : Validated. ✅\n"
                else:
                    # print('not tupple, data: ', data)
                    print('current_result:', current_result)
                    pages_list += f"*[{current_role_name}|{current_role_url}]*: {current_result}\n"
                    pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"
            # =================================

        # здесь обычные пермиссии
            items_list = checking_config_for_service_existence(role_title=position_title, jira_key=jira_key)
            pages_list += '\n\n'
        else:
            # составляем лист всех конфигов которые у нас уже есть в виде списка []
            # print(f"{permissions_for_persona_list[i]['id']} --- {type(permissions_for_persona_list[i])}, this is a regular normal permission")

            print()
            print('items_list for normal permissions:')
            print(items_list)
            print()

            # запрашиваем из ноушена след. по списку пермиссию
            permission_id = permissions_for_persona_list[i]['id']  # id сравниваемой пермиссии
            permission_name = get_notion_page_title(permission_id).json()['properties']['Name']['title'][0]['plain_text']
            permission_url = get_notion_page_title(permission_id).json()['url']
            service_name = re.split('-', permission_name)[-1]
            filename = f".\\roles_configs\\{jira_key}\\{position_title}\\{service_name}_config.json"

            print('permission_name:', permission_name, "; service_name:", service_name)
            permission_config = notion_search_for_permission_block_children(permission_id)
            print('permission_config:', permission_config)

            # т.е. конфиг валидный
            if type(permission_config) == tuple:
                if len(items_list) != 0:
                    for i in range(len(items_list)):
                        print("valid config has found ✅")
                        print('items_list -', items_list)
                        print('service_name from notion -', service_name)
                        print('permission_name -', permission_name)
                        print('permissions_history_check -', permissions_history_check)

                        if service_name in permissions_history_check:
                            print(f'"{service_name}" found in {permissions_history_check}, skipping - was already updated...')
                            continue
                        else:
                            print(service_name, "<->", items_list[i], "comparing...")
                            if re.findall(service_name, items_list[i]):  # если они одинаковые
                                print('нашли такую пермиссию в списке файлов на диске')
                                pages_list += comparing_permission_from_notion_vs_config_on_disk(
                                    filename=filename,
                                    permission_config=permission_config,
                                    pages_list=pages_list,
                                    permission_name=permission_name,
                                    permission_url=permission_url,
                                    service_name=service_name
                                )
                            else:
                                # когда разные сервисы
                                print('НЕ нашли такую пермиссию в списке файлов на диске - проверяем обновлялась ли она уже?')
                                print(permissions_history_check)
                                if service_name in permissions_history_check:
                                    print(f'"{service_name}" found in {permissions_history_check}, passing..., т.е. уже обновлялась')
                                    continue
                                else:
                                    pages_list += comparing_permission_from_notion_vs_config_on_disk(
                                        filename=filename,
                                        permission_config=permission_config,
                                        pages_list=pages_list,
                                        permission_name=permission_name,
                                        permission_url=permission_url,
                                        service_name=service_name
                                    )

                        permissions_history_check.append(service_name)

                # это если список пустой, т.е.никаких пермиссий не добавлено
                else:
                    with open(filename, 'w+') as file:
                        # json.dump('{"test": 1}', file, indent=4)
                        json.dump(permission_config[0], file, indent=4)
                        print("успешно записали", filename)


            # т.е. если конфиг невалидный
            else:  #
                # print('current_result:', permission_config, "- invalid config")
                print("invalid config")
                pages_list += f"*[{permission_name}|{permission_url}]*: {permission_config}\n"
                pages_list += "⬆️Permission is skipped during building *Permissions Tree*!\n"
                pass

    print()

    print('+++++++++++++++++++++++++++++++++++++')
    print(pages_list)
    print()
    print()
    print(len(pages_list))
    print('+++++++++++++++++++++++++++++++++++++')

    send_jira_comment(message=f"Summary after reviewing permissions for *{position_title}* persona:\n{pages_list}."
                              f"*P.S. Remember to move ticket to \"Done\" / \"Rejected\" to rebuild config.*", jira_key=jira_key)

del permissions_history_check