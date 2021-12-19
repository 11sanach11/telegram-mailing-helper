updateDispatchGroupButtons = function () {
    $.ajax({
        type: "GET",
        url: "/templates/dispatch_group_buttons",
        data: "",
        success: function (data) {
            $("#dispatch-group-buttons").replaceWith(data)
        }
    });
}

removeButton = function (gr_id) {
    if (confirm('Вы уверены что хотите удалить кнопку?')) {
        $.ajax({
            type: "POST",
            url: "/api/lists/" + gr_id + "/change",
            data: JSON.stringify({"hidden": true}),
            success: function (data) {
                $("#dispatch-group-info").replaceWith("<div id=\"dispatch-group-info\">Кнопка была успешно удалена</div>")
                updateDispatchGroupButtons();
            },
            error: function () {
                alert("Не удалось удалить кнопку, попробуйте позже");
            }
        });
    }
}

editObject = async function (field, current_dom_id, gr_id) {

    const {value: newName} = await Swal.fire({
        input: 'textarea',
        inputLabel: "Укажите новое значение для поля: ",
        inputPlaceholder: 'Необходимое вам значение...',
        inputValue: $("#" + current_dom_id).html(),
        inputAttributes: {
            'aria-label': 'Type your message here'
        },
        showCancelButton: true
    });
    if (newName != undefined) {
        const sendData = {};
        sendData[field] = newName
        $.ajax({
            type: "POST",
            url: "/api/lists/" + gr_id + "/change",
            data: JSON.stringify(sendData),
            success: function (data) {
                getGroupInfo(gr_id);
                updateDispatchGroupButtons();
            },
            error: function () {
                alert("Не удалось обновить статус, попробуйте позже");
            }
        });
    }
};
getGroupInfo = function (grId) {
    $.ajax({
        type: "GET",
        url: "/templates/lists/" + grId,
        data: "",
        success: function (data) {
            $("#dispatch-group-info").replaceWith(data)
        }
    });
};
changeStateOfDispatchGroup = function (grId, changeAt) {
    $.ajax({
        type: "POST",
        url: "/api/lists/" + grId + "/state",
        data: JSON.stringify({"state": changeAt}),
        success: function (data) {
            getGroupInfo(data.gr_id);
            updateDispatchGroupButtons();
        },
        error: function () {
            alert("Не удалось обновить, попробуйте позже");
        }
    });
};

changeUserState = function (id) {
    $.ajax({
        type: "POST",
        url: "/api/users/state/change",
        data: JSON.stringify({"id": id}),
        success: function (data) {
            $('#user_state_' + id).html(data["localizedState"]);
        },
        contentType: "application/json; charset=utf-8",
        dataType: "json"
    });
};

changeSettings = async function (key) {

    const {value: newValue} = await Swal.fire({
        input: 'textarea',
        inputLabel: "Укажите новое значение для свойства: " + key,
        inputPlaceholder: 'Необходимое вам значение...',
        inputValue: $('#settings-' + key).html(),
        inputAttributes: {
            'aria-label': 'Type your message here'
        },
        showCancelButton: true
    })

    if (newValue) {
        $.ajax({
            type: "POST",
            url: "/api/settings/change",
            data: JSON.stringify({"key": key, "value": newValue}),
            success: function (data) {
                $('#settings-' + data["key"]).html(data["value"]);
            },
            contentType: "application/json; charset=utf-8",
            dataType: "json"
        });
    }
}

loadDataFromFile = function (fileId) {
    let reader = new FileReader();
    reader.onload = function (e) {
        let inputData = e.target.result;
        $('#list_of_items').val(inputData);
        $('#list_of_items_counter').text('Количество строк: ' + inputData.split("\n").length);
    };
    let file = document.getElementById(fileId).files[0];
    reader.readAsText(file);
}

updateCounterForListOfItemsArea = function () {
    $('#list_of_items_counter').text('Количество строк: ' + ($(this).val().split("\n").length));
}

const waitUntilDispatchDataLoaded = function (waitData) {
    let timerInterval;
    Swal.fire({
        title: 'Загружаю данные... Подождите...',
        html: 'Начинается загрузка данных, подождите.',
        timer: 25000,
        didOpen: () => {
            Swal.showLoading()
            const selector = Swal.getHtmlContainer()
            Swal.stopTimer();
            timerInterval = setInterval(() => {
                if (waitData.response) {
                    if (waitData.response.success == true) {
                        $.ajax({
                            type: "GET",
                            url: "/api/lists/" + waitData.response.id + "/state",
                            data: "",
                            success: function (data) {
                                if (data && data.state) {
                                    console.log("updated state: " + JSON.stringify(data));
                                    if (data.state == "starting" || data.state == "inProcess") {
                                        //just update message
                                    } else if (data.state == "finished") {
                                        waitData.form.trigger("reset");
                                        clearInterval(timerInterval);
                                        Swal.hideLoading();
                                        Swal.resumeTimer();
                                    } else {
                                        clearInterval(timerInterval);
                                        Swal.hideLoading();
                                        Swal.resumeTimer();
                                    }
                                    selector.textContent = data.text;
                                } else {
                                    console.error("Wrong answer, please check it. Received: " + data);
                                    clearInterval(timerInterval);
                                    Swal.hideLoading();
                                }
                            },
                            error: function (error) {
                                clearInterval(timerInterval);
                                Swal.hideLoading();
                                selector.textContent = "Что-то пошло не так.";
                                Swal.showValidationMessage("status: " + error.status + ", statusText: " + error.statusText);
                            }
                        });
                    } else {
                        clearInterval(timerInterval);
                        Swal.hideLoading();
                        selector.textContent = "Что-то пошло не так";
                        Swal.showValidationMessage("status: " + waitData.response.status + ", statusText: " + waitData.response.statusText);
                    }
                }
            }, 1000)
        },
        willClose: () => {
            clearInterval(timerInterval);
        }
    });
}

GLOBAL_DIRTY_STORAGE = {};
if (GLOBAL_DIRTY_STORAGE["dispathcer_group_list_of_items_messasge_counter_event"] == undefined) {
    $("#list_of_items").on('change paste', updateCounterForListOfItemsArea);
    GLOBAL_DIRTY_STORAGE["dispathcer_group_list_of_items_messasge_counter_event"] = true;
}
