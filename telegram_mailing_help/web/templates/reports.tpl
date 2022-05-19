<!DOCTYPE html>
<html style="font-size: 16px;">
% include('header.tpl', title='Disp: Отчеты', custom_css='reports.css')
    <section class="u-align-left u-clearfix u-section-2" id="sec-f619">
      <div class="u-clearfix u-sheet u-sheet-1">
        <div class="u-expanded-width u-tab-links-align-left u-tabs u-tabs-1">
          <ul class="u-spacing-5 u-tab-list u-unstyled" role="tablist">
              <li class="u-tab-item" role="presentation">
              <a class="active u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-1" id="link-top_today" href="#top_today" role="tab" aria-controls="top_today" aria-selected="true">Топ по людям за сегодня</a>
            </li>
              <li class="u-tab-item" role="presentation">
                  <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-2" id="link-top_yesterday" href="#top_yesterday" role="tab" aria-controls="top_yesterday" aria-selected="false">Топ по людям за вчера</a>
              </li>
              <li class="u-tab-item" role="presentation">
                  <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-3" id="link-top_last_7_day" href="#top_last_7_day" role="tab" aria-controls="top_last_7_day" aria-selected="false">Топ по людям за последние 7 дней</a>
              </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-2" id="link-top_month" href="#top_month" role="tab" aria-controls="top_month" aria-selected="false">Топ по людям за месяц</a>
            </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-2" id="link-top_today_by_groups" href="#top_today_by_groups" role="tab" aria-controls="top_today_by_groups" aria-selected="false">Взятые кнопки по людям за сегодня</a>
            </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-2" id="link-top_yesterday_by_groups" href="#top_yesterday_by_groups" role="tab" aria-controls="top_yesterday_by_groups" aria-selected="false">Взятые кнопки по людям за вчера</a>
            </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-3" id="link-top_lists_today" href="#top_lists_today" role="tab" aria-controls="top_lists_today" aria-selected="false">Топ по обработанным блокам за сегодня</a>
            </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-3" id="link-top_lists_yesterday" href="#top_lists_yesterday" role="tab" aria-controls="top_lists_yesterday" aria-selected="false">Топ по обработанным блокам за вчера</a>
            </li>
          </ul>
          <div class="u-tab-content">
            <div class="u-container-style u-tab-active u-tab-pane" id="top_today" role="tabpanel" aria-labelledby="link-top_today">
              <div class="u-container-layout u-container-layout-1">
                <div class="u-container-style u-group u-white u-group-1">
                  <div class="u-container-layout u-container-layout-2">
                    <pre>
{{top_today}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_yesterday" role="tabpanel" aria-labelledby="link-top_yesterday">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_yesterday}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_month" role="tabpanel" aria-labelledby="link-top_month">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_month}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_lists_today" role="tabpanel" aria-labelledby="link-top_lists_today">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_lists_today}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_today_by_groups" role="tabpanel" aria-labelledby="link-top_today_by_groups">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_today_by_groups}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_yesterday_by_groups" role="tabpanel" aria-labelledby="link-top_yesterday_by_groups">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_yesterday_by_groups}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_lists_yesterday" role="tabpanel" aria-labelledby="link-top_lists_yesterday">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_lists_yesterday}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div class="u-container-style u-tab-pane" id="top_last_7_day" role="tabpanel" aria-labelledby="link-top_last_7_day">
              <div class="u-container-layout u-valign-top u-container-layout-3">
                <div class="u-container-style u-group u-white u-group-2">
                  <div class="u-container-layout u-container-layout-4">
                    <pre>
{{top_last_7_day}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
% include('footer.tpl')
