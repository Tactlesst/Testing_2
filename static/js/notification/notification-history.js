
// This handles the Notification Page

(function () {
    var allNotifsUrl = '/api/learning-and-development/notifications/all/';
    var markReadUrl = '/api/learning-and-development/notifications/mark-read/';
    var notifSyncStorageKey = 'lds_training_notif_sync_v1';
    var cachedNotifs = [];
    var historyTable = null;

    function broadcastNotifSync(msg) {
        if (!msg) { 
            return;
        }
        msg.ts = (new Date()).getTime();
        try {
            localStorage.setItem(notifSyncStorageKey, JSON.stringify(msg));
        } catch (e) { }
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

    function escapeHtml(s) {
        return $('<div>').text((s || '').toString()).html();
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

    function formatApprovedDate(dateStr) {
        var s = (dateStr || '').toString().trim();
        if (!s) {
            return '';
        }

        // Expected backend format examples:
        // - "Feb 26, 2026 04:48:55 PM"
        // - "Feb 26, 2026 16:48:55 PM" (bad mix of 24h + AM/PM)
        // Normalize to: "Feb 26, 2026 4:48 PM"
        try {
            var m = s.match(/^([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)$/);
            if (m) {
                var datePart = m[1];
                var hh = parseInt(m[2], 10);
                var mm = m[3];
                var ap = m[5];

                if (!isNaN(hh) && hh >= 13) {
                    hh = hh % 12;
                    if (hh === 0) {
                        hh = 12;
                    }
                }

                return datePart + ' ' + String(hh) + ':' + String(mm) + ' ' + ap;
            }
        } catch (e) { }

        // Fallback: if it contains seconds, drop them.
        try {
            var m2 = s.match(/^(.+\d{4})\s+(\d{1,2}:\d{2})(?::\d{2})\s*(AM|PM)?$/);
            if (m2) {
                return (m2[1] + ' ' + m2[2] + (m2[3] ? (' ' + m2[3]) : '')).trim();
            }
        } catch (e2) { }

        return s;
    }

    function statusClass(evt) {
        switch (evt) {
            case 'training_requested':
                return 'badge badge-primary';
            case 'training_approved':
                return 'badge badge-success';
            case 'training_rejected':
                return 'badge badge-danger';
            default:
                return 'badge badge-secondary';
        }
    }

    function statusLabel(evt, fallback) {
        if (fallback) {
            return fallback;
        }
        switch (evt) {
            case 'training_requested':
                return 'Requested';
            case 'training_approved':
                return 'Approved';
            case 'training_rejected':
                return 'Rejected';
            default:
                return 'Updated';
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
        if (!trainingId) {
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

    function renderEmptyRow() {
        var $tb = $('#lds-notif-history-tbody');
        $tb.empty();
        $tb.append(
            '<tr class="text-muted">' +
            '<td colspan="5" class="p-3">No notifications.</td>' +
            '</tr>'
        );
    }

    function initHistoryDataTable() {
        var $table = $('#lds-notif-history-table');
        if (!$table.length) {
            return null;
        }

        if (!$.fn || !$.fn.DataTable) {
            return null;
        }

        var cfg = getNavConfig();
        var showFromCol = !!(cfg && cfg.isAdmin);

        var dt = $table.DataTable({
            paging: true,
            pageLength: 10,
            lengthChange: false,
            searching: true,
            info: true,
            ordering: true,
            autoWidth: false,
            language: {
                emptyTable: 'No notifications.'
            },
            columns: [
                {
                    data: null,
                    render: function (data, type, row) {
                        var title = (row && row.training_title) ? row.training_title : 'Training';
                        var unreadDot = (row && !row.is_read) ? '<span class="bg-primary rounded-circle" style="width:8px;height:8px;display:inline-block;"></span>' : '';
                        return unreadDot + ' <span class="font-weight-bold">' + escapeHtml(truncateText(title, 60)) + '</span>';
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        var from = (row && row.requested_from) ? row.requested_from : '';
                        return escapeHtml(truncateText(from, 40));
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        var date = (row && row.date_approved) ? row.date_approved : '';
                        return escapeHtml(formatApprovedDate(date));
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        var badgeCls = statusClass(row ? row.event : null);
                        var badgeLbl = statusLabel(row ? row.event : null, row ? row.status_display : null);
                        return '<span class="' + escapeHtml(badgeCls) + '">' + escapeHtml(badgeLbl) + '</span>';
                    }
                },
                {
                    data: null,
                    className: 'text-right',
                    orderable: false,
                    render: function (data, type, row) {
                        if (row && !row.is_read) {
                            return '<button type="button" class="btn btn-sm lds-notif-history-mark" data-notif-id="' + escapeHtml(row.id) + '">Mark as Read</button>';
                        }
                        return '<button type="button" class="btn btn-sm btn-light" disabled>Read</button>';
                    }
                }
            ],
            createdRow: function (row, data) {
                $(row)
                    .addClass('lds-notif-history-row')
                    .css('cursor', 'pointer')
                    .attr('data-training-id', (data && data.training_id != null) ? String(data.training_id) : '');
            }
        });

        if (!showFromCol) {
            try {
                dt.column(1).visible(false);
            } catch (e3) { }
        }

        return dt;
    }

    function renderRows(notifs) {
        var $tb = $('#lds-notif-history-tbody');
        if (historyTable) {
            historyTable.clear();
            historyTable.rows.add(notifs || []);
            historyTable.draw();
            return;
        }

        if (!$tb.length) {
            return;
        }

        $tb.empty();

        if (!notifs || !notifs.length) {
            renderEmptyRow();
            return;
        }

        for (var i = 0; i < notifs.length; i++) {
            var n = notifs[i];
            if (!n) {
                continue;
            }

            var title = n.training_title || 'Training';
            var from = n.requested_from || '';
            var date = n.date_approved || '';

            var badgeCls = statusClass(n.event);
            var badgeLbl = statusLabel(n.event, n.status_display);

            var unreadDot = (!n.is_read) ? '<span class="bg-primary rounded-circle" style="width:8px;height:8px;display:inline-block;"></span>' : '';

            var btn = (!n.is_read)
                ? '<button type="button" class="btn btn-sm lds-notif-history-mark" data-notif-id="' + escapeHtml(n.id) + '">Mark as Read</button>'
                : '<button type="button" class="btn btn-sm btn-light" disabled>Read</button>';

            var tr = '';
            tr += '<tr class="lds-notif-history-row" style="cursor:pointer;" data-training-id="' + escapeHtml(n.training_id) + '">';
            tr += '  <td>' + unreadDot + ' <span class="font-weight-bold">' + escapeHtml(truncateText(title, 60)) + '</span></td>';
            tr += '  <td>' + escapeHtml(truncateText(from, 40)) + '</td>';
            tr += '  <td>' + escapeHtml(date) + '</td>';
            tr += '  <td><span class="' + escapeHtml(badgeCls) + '">' + escapeHtml(badgeLbl) + '</span></td>';
            tr += '  <td class="text-right">' + btn + '</td>';
            tr += '</tr>';

            $tb.append(tr);
        }
    }

    function loadHistory() {
        $.ajax({
            url: allNotifsUrl,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                cachedNotifs = (data && data.notifications) ? data.notifications : [];
                renderRows(cachedNotifs);
            },
            error: function () {
                cachedNotifs = [];
                if (historyTable) {
                    historyTable.clear();
                    historyTable.draw();
                } else {
                    renderEmptyRow();
                }
            }
        });
    }

    function renderCurrentPage() {
        renderRows(cachedNotifs);
    }

    $(document).on('click', '.lds-notif-history-row', function (e) {
        if ($(e.target).closest('button').length) {
            return;
        }
        var trainingId = $(this).data('training-id');
        if (trainingId) {
            navigateFromNotif(trainingId);
        }
    });

    $(document).on('click', '.lds-notif-history-mark', function (e) {
        e.preventDefault();
        e.stopPropagation();

        var id = $(this).data('notif-id');
        if (!id) {
            return;
        }

        var $btn = $(this);
        $btn.prop('disabled', true);

        markNotificationRead(id).always(function () {
            loadHistory();
            broadcastNotifSync({ type: 'notif_refresh' });
        });
    });

    $(document).on('click', '#lds-notif-history-mark-all', function (e) {
        e.preventDefault();
        var $btn = $(this);
        $btn.prop('disabled', true);
        markAllNotificationsRead().always(function () {
            loadHistory();
            broadcastNotifSync({ type: 'notif_refresh' });
            $btn.prop('disabled', false);
        });
    });

    $(document).ready(function () {
        if (!$('#lds-notif-history-table').length) {
            return;
        }
        historyTable = initHistoryDataTable();
        loadHistory();
    });
})();
