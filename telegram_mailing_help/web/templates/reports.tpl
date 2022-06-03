<!DOCTYPE html>
<html style="font-size: 16px;">
% include('header.tpl', title='Disp: Отчеты', custom_css='reports.css')
    <section class="u-align-left u-clearfix u-section-2" id="sec-f619">
      <div class="u-clearfix u-sheet u-sheet-1">
        <div class="u-expanded-width u-tab-links-align-left u-tabs u-tabs-1">
          <ul class="u-spacing-5 u-tab-list u-unstyled" role="tablist">
            %for report in reports:
            <li class="u-tab-item" role="presentation">
              <a class="active u-active-palette-1-base u-border-2 u-border-grey-75 u-button-style u-hover-white u-tab-link u-white u-tab-link-1" id="link-{{report.key}}" href="#{{report.key}}" role="tab" aria-controls="{{report.key}}" aria-selected="{{report.selected}}">{{report.title}}</a>
            </li>
            %end
          </ul>
          <div class="u-tab-content">
          %for report in reports:
            <div class="u-container-style u-tab-active u-tab-pane" id="{{report.key}}" role="tabpanel" aria-labelledby="link-{{report.key}}">
              <div class="u-container-layout u-container-layout-1">
                <div class="u-container-style u-group u-white u-group-1">
                  <div class="u-container-layout u-container-layout-2">
                    <pre>
{{report.data}}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            %end
          </div>
        </div>
      </div>
    </section>
% include('footer.tpl')
