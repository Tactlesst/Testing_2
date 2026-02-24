(function () {
            var endpointUrl = '/api/learning-and-development/latest-approved-training/';
            var unreadNotifsUrl = '/api/learning-and-development/notifications/unread/';
            var markReadUrl = '/api/learning-and-development/notifications/mark-read/';
            var storageKey = 'latest_approved_training_id_seen';
            var pollTimer = null;
            var pollDelayMs = 5000;
            var pollDelayMinMs = 5000;
            var pollDelayMaxMs = 60000;

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

                $badge.text(String(val)).show();
            }

            function refreshBadgeFromDom() {
                try {
                    var remaining = $('#lds-notif-items').children('.lds-notif-item').length;
                    setNotifBadge(remaining);
                } catch (e) {
                    setNotifBadge(0);
                }
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

            function alertClassForEvent(evt) {
                switch (evt) {
                    case 'training_requested':
                        return 'alert-primary';
                    case 'training_approved':
                        return 'alert-success';
                    case 'training_rejected':
                        return 'alert-danger';
                    default:
                        return 'alert-info';
                }
            }

            function prependNotifItem(title, message, notifId, event) {
                var $wrap = $('#lds-notif-items');
                if (!$wrap.length) {
                    return;
                }

                $wrap.find('.lds-notif-empty').remove();

                var fullTitle = title || 'Training';
                var fullMsg = message || 'has been approved, make sure to check your Dashboard.';
                var safeTitle = truncateText(fullTitle, 40);
                var safeMsg = truncateText(fullMsg, 70);

                var idAttr = (notifId) ? (' data-notif-id="' + String(notifId) + '" ') : '';
                var klass = alertClassForEvent(event);

                var html = '';
                html += '<div class="alert ' + klass + ' mb-2 p-2 lds-notif-item"' + idAttr + '>';
                html += '  <div class="d-flex justify-content-between align-items-start">';
                html += '    <div class="pr-2" style="min-width:0;">';
                html += '      <div class="font-weight-bold text-truncate" title="' + $('<div>').text(fullTitle).html() + '" style="max-width: 210px;">' + $('<div>').text(safeTitle).html() + '</div>';
                html += '      <div class="small text-truncate" title="' + $('<div>').text(fullMsg).html() + '" style="max-width: 210px;">' + $('<div>').text(safeMsg).html() + '</div>';
                html += '    </div>';
                html += '    <button type="button" class="btn btn-sm btn-light lds-notif-mark-seen"' + idAttr + '><img src="'+ eyeIconURL +'"></button>';
                html += '  </div>';
                html += '</div>';

                $wrap.prepend(html);

                var maxItems = 5;
                var $items = $wrap.children('.lds-notif-item');
                if ($items.length > maxItems) {
                    $items.slice(maxItems).remove();
                }

                refreshBadgeFromDom();
            }

            function renderEmptyState() {
                var $wrap = $('#lds-notif-items');
                if (!$wrap.length) {
                    return;
                }
                $wrap.empty();
                $wrap.append('<div class="lds-notif-empty text-muted small p-2">No unread notifications.</div>');
                setNotifBadge(0);
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
                            renderEmptyState();
                            return;
                        }

                        for (var i = 0; i < data.notifications.length; i++) {
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

                            prependNotifItem(
                                n.training_title || "Training",
                                msg,
                                n.id,
                                n.event
                            );
                        }
                        setNotifBadge(data.count || data.notifications.length);
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
                                prependNotifItem(payload.training_title || 'Training', msg, payload.notif_id, payload.event);
                                break;

                            case "training_approved":
                                var msg = (payload.requested_from || 'An admin') + " has approved the training.";
                                prependNotifItem(payload.training_title || 'Training', msg, payload.notif_id, payload.event);
                                showApprovedTrainingAlert();
                                break;

                            case "training_rejected":
                                var msg = (payload.requested_from || 'An admin') + " has rejected the training.";
                                prependNotifItem(payload.training_title || 'Training', msg, payload.notif_id, payload.event);
                                break;

                            case "training_request_resolved":
                                try {
                                    var $item = $('.lds-notif-item[data-notif-id="' + String(payload.notif_id) + '"]');
                                    if ($item.length) {
                                        $item.remove();
                                        if ($('#lds-notif-items').children('.lds-notif-item').length === 0) {
                                            renderEmptyState();
                                        } else {
                                            refreshBadgeFromDom();
                                        }
                                    }
                                } catch (e) {}
                                break;
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

                        showApprovedTrainingAlert();
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
                loadUnreadNotifications();
                connectLdsNotifWebSocket();
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

            $(document).on('click', '.lds-notif-mark-seen', function (e) {
                e.preventDefault();
                e.stopPropagation();

                var id = $(this).data('notif-id');
                if (!id) {
                    return;
                }

                var $el = $('.lds-notif-item[data-notif-id="' + String(id) + '"]');
                markNotificationRead(id).always(function () {
                    $el.remove();
                    if ($('#lds-notif-items').children('.lds-notif-item').length === 0) {
                        renderEmptyState();
                    } else {
                        refreshBadgeFromDom();
                    }
                });
            });

            $(document).on('click', '#lds-notif-mark-all', function (e) {
                e.preventDefault();
                markAllNotificationsRead().always(function () {
                    loadUnreadNotifications();
                });
            });
        })();