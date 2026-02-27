
// This handles Notification from Layout
// Note that the functions is also being used as well in notification page

(function () {
    var endpointUrl = '/api/learning-and-development/latest-approved-training/';
    var unreadNotifsUrl = '/api/learning-and-development/notifications/unread/';
    var allNotifsUrl = '/api/learning-and-development/notifications/all/';
    var markReadUrl = '/api/learning-and-development/notifications/mark-read/';
    var storageKey = 'latest_approved_training_id_seen';
    var unreadCount = null;
    var notifSyncChannel = null;
    var notifSyncStorageKey = 'lds_training_notif_sync_v1';
    var pollTimer = null;
    var pollDelayMs = 5000;
    var pollDelayMinMs = 5000;
    var pollDelayMaxMs = 60000;

    function initNotifSync() {
        try {
            if ('BroadcastChannel' in window) {
                notifSyncChannel = new BroadcastChannel('lds_training_notifications');
                notifSyncChannel.onmessage = function (ev) {
                    try {
                        handleNotifSyncMessage(ev && ev.data ? ev.data : null);
                    } catch (e) { }
                };
            }
        } catch (e) {
            notifSyncChannel = null;
        }

        try {
            window.addEventListener('storage', function (ev) {
                if (!ev || ev.key !== notifSyncStorageKey || !ev.newValue) {
                    return;
                }
                try {
                    handleNotifSyncMessage(JSON.parse(ev.newValue));
                } catch (e) { }
            });
        } catch (e) { }
    }

    function broadcastNotifSync(msg) {
        if (!msg) {
            return;
        }
        msg.ts = (new Date()).getTime();

        try {
            if (notifSyncChannel) {
                notifSyncChannel.postMessage(msg);
            }
        } catch (e) { }

        try {
            localStorage.setItem(notifSyncStorageKey, JSON.stringify(msg));
        } catch (e) { }
    }

    function handleNotifSyncMessage(msg) {
        if (!msg || !msg.type) {
            return;
        }
        if (msg.type === 'notif_removed' && msg.notif_id) {
            removeNotifFromUi(msg.notif_id, false);
            return;
        }
        if (msg.type === 'notif_cleared') {
            if (isHistoryPage()) {
                loadAllNotificationsHistory();
            } else {
                renderEmptyState(false);
            }
            return;
        }
        if (msg.type === 'notif_refresh') {
            if (isHistoryPage()) {
                loadAllNotificationsHistory();
            } else {
                loadUnreadNotifications();
            }
            return;
        }
    }

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function setNotifBadge(count) {
        var $badge = $('#lds-notif-badge');
        if (!$badge.length) {
            return;
        }

        var val = parseInt(count || 0, 10);
        if (isNaN(val) || val <= 0) {
            $badge.hide().text('0');
            return;
        }

        if (val > 5) {
            $badge.text('5+').show();
            return;
        }

        $badge.text(String(val)).show();
    }

    function syncBadge() {
        if (unreadCount === null || typeof unreadCount === 'undefined') {
            unreadCount = 0;
        }
        setNotifBadge(unreadCount);
    }

    function recomputeUnreadCountFromDropdownUi() {
        try {
            if (isHistoryPage()) {
                return;
            }
            var $wrap = $('#lds-notif-items');
            if (!$wrap.length) {
                return;
            }
            unreadCount = $wrap.children('.lds-notif-row').length;
        } catch (e) { }
    }

    function truncateText(text, maxLen) {
        var s = (text || '').toString();
        var max = parseInt(maxLen || 45, 10);
        if (!max || max < 10) {
            max = 45;
        }
        if (s.length <= max) {
            return s;
        }
        return s.substring(0, max - 3) + '...';
    }

    function textClassForEvent(evt) {
        return 'text-dark';
    }

    function escapeHtml(s) {
        return $('<div>').text((s || '').toString()).html();
    }

    function canNavigateFromNotif() {
        try {
            return typeof window.ldsNotifCanNavigate === 'undefined' ? true : !!window.ldsNotifCanNavigate;
        } catch (e) {
            return true;
        }
    }

    function getNavConfig() {
        var $dd = $('#notificationDropdown');
        var cfg = {
            isAdmin: false,
            adminUrl: null,
            requesterTpl: null,
        };

        if (!$dd.length) {
            return cfg;
        }

        try {
            var isSuper = String($dd.data('lds-notif-is-admin') || '0') === '1';
            var isLdAdmin = String($dd.data('lds-notif-is-ld-admin') || '0') === '1';
            cfg.isAdmin = isSuper || isLdAdmin;
        } catch (e) {
            cfg.isAdmin = false;
        }

        try {
            cfg.adminUrl = $dd.data('lds-notif-admin-url') || null;
        } catch (e) {
            cfg.adminUrl = null;
        }

        try {
            cfg.requesterTpl = $dd.data('lds-notif-requester-details-url-template') || null;
        } catch (e) {
            cfg.requesterTpl = null;
        }

        return cfg;
    }

    function navigateFromNotif(trainingId) {
        if (!trainingId || !canNavigateFromNotif()) {
            return;
        }

        var cfg = getNavConfig();

        if (cfg.isAdmin) {
            if (cfg.adminUrl) {
                window.location.href = String(cfg.adminUrl) + '?open_training_id=' + encodeURIComponent(String(trainingId));
            }
            return;
        }

        if (cfg.requesterTpl) {
            window.location.href = String(cfg.requesterTpl).replace('__ID__', encodeURIComponent(String(trainingId)));
        }
    }

    function loadAllNotificationsHistory() {
        $.ajax({
            url: allNotifsUrl,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                var $wrap = $('#lds-notif-history-items');
                if (!$wrap.length) {
                    return;
                }

                $wrap.empty();

                if (!data || !data.notifications || !data.notifications.length) {
                    $wrap.append('<div class="lds-notif-empty text-muted small p-2">No notifications.</div>');
                    return;
                }

                for (var i = data.notifications.length - 1; i >= 0; i--) {
                    var n = data.notifications[i];
                    if (!n) {
                        continue;
                    }

                    var msg = '';
                    switch (n.event) {
                        case "training_requested":
                            msg = (n.requested_from || 'A requester') + " has requested training approval.";
                            break;
                        case "training_approved":
                            msg = (n.requested_from || 'An admin') + " has approved the training.";
                            break;
                        case "training_rejected":
                            msg = (n.requested_from || 'An admin') + " has rejected the training.";
                            break;
                        default:
                            msg = "Training status updated.";
                    }

                    prependNotifItemTo(
                        $wrap,
                        n.training_title || 'Training',
                        msg,
                        n.id,
                        n.event,
                        n.training_id,
                        n.date_requested,
                        n.date_approved,
                        n.time_ago,
                        !n.is_read,
                        0
                    );
                }
            }
        });
    }

    function isHistoryPage() {
        try {
            return $('#lds-notif-history-root[data-lds-notif-history="1"]').length > 0;
        } catch (e) {
            return false;
        }
    }

    function getNotifWrap() {
        if (isHistoryPage()) {
            return $('#lds-notif-history-items');
        }
        return $('#lds-notif-items');
    }

    function prependNotifItemTo($wrap, title, message, notifId, event, trainingId, dateRequested, dateApproved, timeAgoText, isUnread, capItems) {
        if (!$wrap || !$wrap.length) {
            return;
        }

        if (notifId && $wrap.find('.lds-notif-item[data-notif-id="' + String(notifId) + '"]').length) {
            return;
        }

        $wrap.find('.lds-notif-empty').remove();

        var fullTitle = title || 'Training';
        var fullMsg = message || 'has been approved, make sure to check your Dashboard.';
        var safeTitle = truncateText(fullTitle, 40);
        var safeMsg = truncateText(fullMsg, 70);

        var idAttr = (notifId) ? (' data-notif-id="' + String(notifId) + '" ') : '';
        var trAttr = (trainingId) ? (' data-training-id="' + String(trainingId) + '" ') : '';
        var textKlass = textClassForEvent(event);

        var unreadFlag = (typeof isUnread === 'undefined' || isUnread === null) ? true : !!isUnread;

        function timeAgoFromDateString(dateStr) {
            if (!dateStr) {
                return 'Just now';
            }
            var d = null;
            try {
                d = new Date(dateStr);
                if (isNaN(d.getTime())) {
                    d = null;
                }
            } catch (e) {
                d = null;
            }
            if (!d) {
                return 'Just now';
            }

            var diff = Math.max(0, (new Date()).getTime() - d.getTime());
            var sec = Math.floor(diff / 1000);
            if (sec < 60) return sec <= 5 ? 'Just now' : (sec + 's');
            var min = Math.floor(sec / 60);
            if (min < 60) return (min + 'm');
            var hr = Math.floor(min / 60);
            if (hr < 24) return (hr + 'h');
            var day = Math.floor(hr / 24);
            if (day < 7) return (day + 'd');
            var wk = Math.floor(day / 7);
            if (wk < 4) return (wk + 'w');
            var mo = Math.floor(day / 30);
            if (mo < 12) return (mo + 'mo');
            var yr = Math.floor(day / 365);
            return (yr + 'y');
        }

        var timeAgo = (timeAgoText && String(timeAgoText).trim())
            ? String(timeAgoText)
            : timeAgoFromDateString(dateRequested || dateApproved);

        var html = '';

        html += '<div class="d-flex align-items-start p-2 mb-1 rounded lds-notif-row position-relative bg-white" ' + idAttr + trAttr + ' style="cursor:pointer; background-color:#fff;">';

        html += '  <a href="javascript:;" class="d-flex flex-grow-1 text-decoration-none text-dark lds-notif-item" ' + idAttr + trAttr + '>';

        html += '    <!-- Content -->';
        html += '    <div class="flex-grow-1" style="min-width:0;">';
        html += '      <div class="small">';
        html += '        <span class="font-weight-bold ' + escapeHtml(textKlass) + '">' + escapeHtml(safeTitle) + '</span> ';
        html += '        <span class="' + escapeHtml(textKlass) + '">' + escapeHtml(safeMsg) + '</span>';
        html += '      </div>';
        html += '      <div class="text-muted small">' + timeAgo + '</div>';
        html += '    </div>';

        html += '  </a>';

        html += '  <!-- Right Side -->';
        html += '  <div class="d-flex flex-column align-items-center justify-content-between ml-2">';
        html += '    <button type="button" class="btn btn-sm btn-light rounded-circle p-1 lds-notif-mark-seen" ' + idAttr + trAttr + '>';
        html += '      <img src="' + escapeHtml((typeof eyeIconURL !== "undefined") ? eyeIconURL : "") + '" width="14">';
        html += '    </button>';
        html += '  </div>';

        html += '</div>';

        $wrap.prepend(html);

        var maxItems = parseInt(capItems || 0, 10);
        if (!isNaN(maxItems) && maxItems > 0) {
            var $rows = $wrap.children('.lds-notif-row');
            if ($rows.length > maxItems) {
                $rows.slice(maxItems).remove();
            }
        }
    }

    function prependNotifItem(title, message, notifId, event, trainingId, dateRequested, dateApproved, timeAgoText) {
        var $wrap = getNotifWrap();
        prependNotifItemTo($wrap, title, message, notifId, event, trainingId, dateRequested, dateApproved, timeAgoText, true, 5);
    }

    function markHistoryRowRead(notifId) {
        if (!notifId) {
            return;
        }
        var $el = $('#lds-notif-history-items').find('.lds-notif-item[data-notif-id="' + String(notifId) + '"]');
        if (!$el.length) {
            return;
        }
        try {
            $el.closest('.lds-notif-row').find('.lds-notif-unread-dot').hide();
        } catch (e) { }
    }

    function renderEmptyState(shouldBroadcast) {
        var $wrap = getNotifWrap();
        if (!$wrap.length) {
            return;
        }
        $wrap.empty();
        if (isHistoryPage()) {
            $wrap.append('<div class="lds-notif-empty text-muted small p-2">No notifications.</div>');
        } else {
            $wrap.append('<div class="lds-notif-empty text-muted small p-2">No unread notifications.</div>');
        }
        unreadCount = 0;
        syncBadge();

        if (shouldBroadcast !== false) {
            broadcastNotifSync({ type: 'notif_cleared' });
        }
    }

    function removeNotifFromUi(notifId, shouldBroadcast) {
        if (!notifId) {
            return;
        }

        var $el = $('.lds-notif-item[data-notif-id="' + String(notifId) + '"]');
        var removed = false;
        if ($el.length) {
            $el.closest('.lds-notif-row').remove();
            removed = true;
        }

        if (removed) {
            if (unreadCount === null || typeof unreadCount === 'undefined') {
                recomputeUnreadCountFromDropdownUi();
            } else {
                unreadCount = Math.max(0, unreadCount - 1);
            }
        } else {
            if (unreadCount === null || typeof unreadCount === 'undefined') {
                unreadCount = 0;
            }
        }

        if ($('#lds-notif-items').children('.lds-notif-row').length === 0) {
            renderEmptyState(false);
        } else {
            syncBadge();
        }

        if (shouldBroadcast !== false) {
            broadcastNotifSync({ type: 'notif_removed', notif_id: notifId });
        }
    }

    function loadUnreadNotifications() {
        $.ajax({
            url: unreadNotifsUrl,

            type: 'GET',
            dataType: 'json',
            success: function (data) {
                var $wrap = $('#lds-notif-items');
                if (!$wrap.length) {
                    return;
                }

                $wrap.empty();

                if (!data || !data.notifications || !data.notifications.length) {
                    renderEmptyState(false);
                    return;
                }

                unreadCount = parseInt(data.count || data.notifications.length || 0, 10);
                if (isNaN(unreadCount) || unreadCount < 0) {
                    unreadCount = 0;
                }

                for (var i = data.notifications.length - 1; i >= 0; i--) {
                    var n = data.notifications[i];
                    if (!n) {
                        continue;
                    }

                    var msg = '';

                    switch (n.event) {
                        case "training_requested":
                            msg = (n.requested_from || 'A requester') + " has requested training approval.";
                            break;

                        case "training_approved":
                            msg = " has been approved for training.";
                            break;

                        case "training_rejected":
                            msg = " has been rejected for training.";
                            break;

                        default:
                            msg = "Training status updated.";
                    }

                    prependNotifItem(
                        n.training_title || "Training",
                        msg,
                        n.id,
                        n.event,
                        n.training_id,
                        n.date_requested,
                        n.date_approved,
                        n.time_ago
                    );
                }
                syncBadge();
            }
        });
    }

    function markNotificationRead(id) {
        return $.ajax({
            url: markReadUrl,
            type: 'POST',
            dataType: 'json',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: {
                'id': id
            }
        });
    }

    function markAllNotificationsRead() {
        return $.ajax({
            url: markReadUrl,
            type: 'POST',
            dataType: 'json',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: {
                'is_read': 1
            }
        });
    }

    function connectLdsNotifWebSocket() {
        var ws = null;
        if ('WebSocket' in window) {
            var scheme = (window.location.protocol === 'https:') ? 'wss://' : 'ws://';
            var wsUrl = scheme + window.location.host + '/ws/lds/notifications/';
            try {
                ws = new WebSocket(wsUrl);
            } catch (e) {
                ws = null;
            }
        }

        if (ws) {
            ws.onmessage = function (event) {
                var payload = null;
                try {
                    payload = JSON.parse(event.data);
                } catch (e) {
                    payload = null;
                }

                if (!payload || !payload.event) {
                    return;
                }

                switch (payload.event) {
                    case "training_requested":
                        var msg = (payload.requested_from || 'A requester') + " has requested training approval.";
                        if (unreadCount === null || typeof unreadCount === 'undefined') {
                            unreadCount = 0;
                        }
                        unreadCount = unreadCount + 1;
                        prependNotifItem(payload.training_title || 'Training', msg, payload.notif_id, payload.event, payload.training_id, payload.date_requested || null, payload.date_approved || null, payload.time_ago || null);
                        syncBadge();
                        break;

                    case "training_approved":
                        var msg = (payload.requested_from || 'An admin') + " has approved the training.";
                        if (unreadCount === null || typeof unreadCount === 'undefined') {
                            unreadCount = 0;
                        }
                        unreadCount = unreadCount + 1;
                        prependNotifItem(payload.training_title || 'Training', msg, payload.notif_id, payload.event, payload.training_id, payload.date_requested || null, payload.date_approved || null, payload.time_ago || null);
                        syncBadge();
                        if (typeof showApprovedTrainingAlert === 'function') {
                            showApprovedTrainingAlert();
                        }
                        break;

                    case "training_rejected":
                        var msg = (payload.requested_from || 'An admin') + " has rejected the training.";
                        if (unreadCount === null || typeof unreadCount === 'undefined') {
                            unreadCount = 0;
                        }
                        unreadCount = unreadCount + 1;
                        prependNotifItem(payload.training_title || 'Training', msg, payload.notif_id, payload.event, payload.training_id, payload.date_requested || null, payload.date_approved || null, payload.time_ago || null);
                        syncBadge();
                        break;

                    case "training_request_resolved":
                        try {
                            removeNotifFromUi(payload.notif_id, true);
                        } catch (e) { }
                }
            };

            ws.onclose = function () {
                setTimeout(function () {
                    connectLdsNotifWebSocket();
                }, 5000);
            };

            ws.onerror = function () {
                try {
                    ws.close();
                } catch (e) { }
            };

            return;
        }
    }

    function scheduleNextPoll(delayMs) {
        clearPollTimer();
        pollTimer = setTimeout(function () {
            pollLatestApprovedTraining();
        }, delayMs);
    }

    function isPageVisible() {
        return document.visibilityState === 'visible';
    }

    function pollLatestApprovedTraining() {
        if (!isPageVisible()) {
            scheduleNextPoll(pollDelayMaxMs);
            return;
        }
        $.ajax({
            url: endpointUrl,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                var foundNew = false;
                if (!data || !data.has_latest) {
                    pollDelayMs = Math.min(pollDelayMaxMs, pollDelayMs * 2);
                    scheduleNextPoll(pollDelayMs);
                    return;
                }

                var latestId = data.id;
                if (!latestId) {
                    pollDelayMs = Math.min(pollDelayMaxMs, pollDelayMs * 2);
                    scheduleNextPoll(pollDelayMs);
                    return;
                }

                var seenId = null;
                try {
                    seenId = localStorage.getItem(storageKey);
                } catch (e) {
                    seenId = null;
                }

                if (seenId && String(seenId) === String(latestId)) {
                    pollDelayMs = Math.min(pollDelayMaxMs, pollDelayMs * 2);
                    scheduleNextPoll(pollDelayMs);
                    return;
                }

                try {
                    localStorage.setItem(storageKey, String(latestId));
                } catch (e) { }

                if (typeof showApprovedTrainingAlert === 'function') {
                    showApprovedTrainingAlert();
                }
                foundNew = true;

                if (foundNew) {
                    pollDelayMs = pollDelayMinMs;
                }
                scheduleNextPoll(pollDelayMs);
            }
        }).fail(function () {
            pollDelayMs = Math.min(pollDelayMaxMs, pollDelayMs * 2);
            scheduleNextPoll(pollDelayMs);
        });
    }

    $(document).ready(function () {
        initNotifSync();
        if (isHistoryPage()) {
            loadAllNotificationsHistory();
        } else {
            loadUnreadNotifications();
            connectLdsNotifWebSocket();
        }
        pollDelayMs = pollDelayMinMs;
        pollLatestApprovedTraining();

        document.addEventListener('visibilitychange', function () {
            if (isPageVisible()) {
                pollDelayMs = pollDelayMinMs;
                pollLatestApprovedTraining();
            }
        });
    });

    $(document).on('shown.bs.dropdown', '#notificationDropdown', function () {
        loadUnreadNotifications();
    });

    $(document).on('click', '.lds-notif-item', function (e) {
        e.preventDefault();
        var trainingId = $(this).data('training-id');
        if (trainingId) {
            navigateFromNotif(trainingId);
        }
    });

    $(document).on('click', '.lds-notif-mark-seen', function (e) {
        e.preventDefault();
        e.stopPropagation();

        var id = $(this).data('notif-id');
        if (!id) {
            return;
        }

        if (isHistoryPage()) {
            markHistoryRowRead(id);
        } else {
            removeNotifFromUi(id, true);
        }

        markNotificationRead(id)
            .always(function () {
                if (!isHistoryPage()) {
                    loadUnreadNotifications();
                    broadcastNotifSync({ type: 'notif_refresh' });
                }
            })
            .fail(function () {
                if (isHistoryPage()) {
                    loadAllNotificationsHistory();
                }
            });
    });

    $(document).on('click', '#lds-notif-mark-all', function (e) {
        e.preventDefault();
        if (isHistoryPage()) {
            markAllNotificationsRead().always(function () {
                loadAllNotificationsHistory();
                broadcastNotifSync({ type: 'notif_refresh' });
            });
            return;
        }

        renderEmptyState(true);

        markAllNotificationsRead().fail(function () {
            loadUnreadNotifications();
            broadcastNotifSync({ type: 'notif_refresh' });
        });
    });
})();