

function Alert (div, raw_data) {
  this.$div = div;
  for (var k in raw_data) {
    this[k] = raw_data[k];
  }

  this._ = function(id) {
    return this.$div.find('#' + id);
  }

  this.init_render = function() {
    this._('msg').text(this.msg);
    this._('detail').toggle(Boolean(this.url));
    this._('url').attr('href', this.url);

  }
}

function render_alert(alert) {

  render_status(alert);

  alert.num_comments = 0;
  var $comments = $div.find('#comments');
  $(alert.comments).each(function (i, comment) {
    $comment = render_comment(comment, alert);
    $comments.append($comment);
  });
  $comments.append('<input id="newcomment" style="width: 30em;"> <a id="addcomment" href="#">add comment</a><span id="pleasewait">please wait&hellip;</span>');
  $comments.find('#pleasewait').hide();
  $comments.find('#addcomment').click(function () { add_comment(alert); });

  $div.find('#pendingaction').toggle(false);

  var $toggle = $div.find('#toggle');
  var toggle_text = function(expanded) {
    var caption = (expanded ? 'hide' : 'show ' + (alert.num_comments > 0 ? 'comments(' + alert.num_comments + ')' : 'history'));
    $toggle.text(caption);
  }
  $toggle.click(function() { toggle_alert_detail(alert); });
  $comments.hide();
  toggle_text(false);
}

function toggle_alert_detail(alert, show) {
  $detail = alert.div.find('#alertdetail');
  if (show == null) {
    var show = !$detail.filter(':visible').length;
  }
  //toggle_text(show);
  if (show) {
    $detail.slideDown();
  } else {
    $detail.slideUp();
  }
}

function render_status(alert) {
  var status_text = {
    'new': function() { return 'new'; },
    'fu': function() { return alert.owner + ' is following up'; },
    'esc': function() { return 'escalated to ' + alert.owner; },
    'closed': function() { return 'closed'; },
  }[alert.status]();
  alert.div.find('#status').text(status_text);

  var $actions = alert.div.find('#actions');
  $actions.empty();
  $(alert.actions).each(function(i, action) {
    var action_caption = {
      'fu': 'follow up',
      'resolve': 'resolve',
      'esc': 'escalate',
    }[action];
    var $action = $('<a href="#">' + action_caption + '</a>');
    $action.click(function() { pending_action(alert, action); });
    $actions.append($action);
    if (i < alert.actions.length - 1) {
      $actions.append(' &middot; ');
    }
  });
}

function pending_action(alert, action) {
  var $pend = alert.div.find('#pendingaction');
  $pend.slideToggle(true);
}

function take_action(alert, action) {
  $.post('{% url alerts.ajax.alert_action %}', {alert_id: alert.id, action: action}, function(data) {
    var mod_alert = clone_alert(alert, data);
    if (mod_alert.status != 'closed') {
      render_status(mod_alert);
    } else {
      mod_alert.div.slideUp();
    }
  }, 'json');
}

function clone_alert(alert1, alert2) {
  alert2.div = alert1.div;
  alert2.num_comments = alert1.num_comments;
  return alert2;
}

function render_comment(comment, alert) {
  $comment = $('<div><span id="text"></span> <span style="color: #d77;">by</span> <span id="author"></span> <span style="color: #d77;">at</span> <span id="date"></span></div>');
  if (comment.is_system) {
    $comment.css('background-color', '#ccf');
  }
  $comment.find('#text').text(comment.text);
  $comment.find('#author').text(comment.author);
  $comment.find('#date').text(comment.date_fmt);
  if (!comment.is_system) {
    alert.num_comments++;
  }
  return $comment;
}

function add_comment(alert){
  var comment_text = $.trim(alert.div.find('#newcomment').val());
  if (!comment_text)
    return;

  alert.div.find('#addcomment').hide();
  alert.div.find('#pleasewait').show();
  $.post('{% url alerts.ajax.add_comment %}', {alert_id: alert.id, text: alert.div.find('#newcomment').val()}, function(data) {
    alert.div.find('#newcomment').before(render_comment(data, alert));
    alert.div.find('#newcomment').val('');

    alert.div.find('#addcomment').show();
    alert.div.find('#pleasewait').hide();
  }, 'json');
}