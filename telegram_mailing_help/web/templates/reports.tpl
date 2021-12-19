<!DOCTYPE html>
<html style="font-size: 16px;">
% include('header.tpl', title='Disp: Отчеты', custom_css='reports.css')
    <section class="u-align-left u-clearfix u-section-2" id="sec-f619">
      <div class="u-clearfix u-sheet u-sheet-1">
        <div class="u-expanded-width u-tab-links-align-left u-tabs u-tabs-1">
          <ul class="u-spacing-5 u-tab-list u-unstyled" role="tablist">
              <li class="u-tab-item" role="presentation">
              <a class="active u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-1" id="link-tab-1443" href="#tab-1443" role="tab" aria-controls="tab-1443" aria-selected="true">Топ по людям за сегодня</a>
            </li>
              <li class="u-tab-item" role="presentation">
                  <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-2" id="link-tab-1444" href="#tab-1444" role="tab" aria-controls="tab-1444" aria-selected="false">Топ по людям за вчера</a>
              </li>
              <li class="u-tab-item" role="presentation">
                  <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-3" id="link-tab-02a10" href="#tab-02a10" role="tab" aria-controls="tab-02a10" aria-selected="false">Топ по людям за последние 7 дней</a>
              </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-2" id="link-tab-02a7" href="#tab-02a7" role="tab" aria-controls="tab-02a7" aria-selected="false">Топ по людям за месяц</a>
            </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-3" id="link-tab-02a8" href="#tab-02a8" role="tab" aria-controls="tab-02a8" aria-selected="false">Топ по обработанным блокам за сегодня</a>
            </li>
              <li class="u-tab-item" role="presentation">
              <a class="u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-3" id="link-tab-02a9" href="#tab-02a9" role="tab" aria-controls="tab-02a9" aria-selected="false">Топ по обработанным блокам за вчера</a>
            </li>
          </ul>
          <div class="u-tab-content">
            <div class="u-container-style u-tab-active u-tab-pane" id="tab-1443" role="tabpanel" aria-labelledby="link-tab-1443">
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
            <div class="u-container-style u-tab-pane" id="tab-1444" role="tabpanel" aria-labelledby="link-tab-1444">
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
            <div class="u-container-style u-tab-pane" id="tab-02a7" role="tabpanel" aria-labelledby="link-tab-02a7">
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
            <div class="u-container-style u-tab-pane" id="tab-02a8" role="tabpanel" aria-labelledby="link-tab-02a8">
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
            <div class="u-container-style u-tab-pane" id="tab-02a9" role="tabpanel" aria-labelledby="link-tab-02a9">
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
            <div class="u-container-style u-tab-pane" id="tab-02a10" role="tabpanel" aria-labelledby="link-tab-02a10">
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
