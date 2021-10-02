<div id="dispatch-group-info">
    <ul class="u-text u-text-1">
        <li>Название: <span id="dispatch-group-name-group-info">{{data["info"].dispatch_group_name}}</span> -> <a href="#a" onclick="editObject('dispatch_group_name','dispatch-group-name-group-info', {{data["info"].id}})">Редактировать</a></li>
        <li>Описание: <span id="description-group-info">{{data["info"].description}}</span> -> <a href="#a" onclick="editObject('description','description-group-info', {{data["info"].id}})">Редактировать</a></li>
        <li>Приоритет (целое число): <span id="priority-group-info">{{data["info"].priority}}</span> -> <a href="#a" onclick="editObject('priority','priority-group-info', {{data["info"].id}})">Редактировать</a></li>
        <li>Выводить описания с каждым блоком (1-выводить, 0-нет): <span id="show_comment_with_block-group-info">{{data["info"].show_comment_with_block}}</span> -> <a href="#a" onclick="editObject('show_comment_with_block','show_comment_with_block-group-info', {{data["info"].id}})">Редактировать</a></li>
        <li>Повторно отдавать блок раз (целое число): {{data["info"].repeat}}</li>
        <li>Количество блоков: {{data["info"].count}}</li>
        <li>Кол-во назначенных блоков: {{data["info"].assigned_count}}</li>
        <li>Кол-во свободных блоков: {{data["info"].free_count}}</li>
    </ul>
    <a href="#a" onclick="changeStateOfDispatchGroup('{{data["info"].id}}','{{data["state"]["value"]}}')">{{data["state"]["text"]}}</a>
    % if not data["info"].enabled:
    <p/><a href="#a" style="color:red" onclick="removeButton({{data['info'].id}})">УДАЛИТЬ КНОПКУ</a>
    % end
</div>