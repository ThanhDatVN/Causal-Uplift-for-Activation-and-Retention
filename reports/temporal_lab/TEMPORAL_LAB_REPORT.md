# Temporal retention laboratory — known-counterfactual mock data

> Đây là mechanism test, không phải bằng chứng hiệu quả kinh doanh ngoài đời.

## Pain point được làm rõ bằng số

Generator tạo 80,157 customer-month của 6,000 khách. Sau regime change, true ATE đổi từ 0.649% thành -0.105%; tỷ lệ offer gây hại tăng từ 46.4% lên 64.3%. Một churn score vẫn có thể tốt trong khi chính sách giữ chân đã mất tác dụng.

Row-random AP = 0.0873, out-of-time AP = 0.1209, nhưng base rate cũng đổi nên AP thô không thể dùng để kết luận drift. Brier skill giảm từ 0.0168 xuống 0.0046; đây mới là bằng chứng calibration gần như mất hết giá trị sau regime change. Chỉ protocol out-of-time hợp lệ cho deployment.

## Policy được khóa

Validation DR chọn `no_contact` ở 0% capacity. Trên test, true net value = 0.00, true expected prevented churn = 0.00, harmful contacts = 0.0%, regret so với best oracle khả dụng = 6806.40.

Ở cùng 20% capacity trên test, risk targeting tạo true value -2813.34 và gửi offer có hại cho 40.5% nhóm được chọn. S-learner tạo 1133.39, harmful contacts 25.8%; oracle value là 5814.90. Đây là phép đo cụ thể của khoảng cách risk ≠ persuadability, không phải nhận xét định tính.

## Continuous rolling refit

 month_index snapshot_month  training_rows  active_customers  selected_n  true_net_value  oracle_net_value    regret  true_mean_cate  harmful_offer_share
          15     2025-04-01          70980              3246           0             0.0         2760.2401 2760.2401             0.0                  0.0
          16     2025-05-01          74226              3057           0             0.0         2013.7758 2013.7758             0.0                  0.0
          17     2025-06-01          77283              2874           0             0.0         2032.4188 2032.4188             0.0                  0.0

## Điều generator cố ý mô phỏng

- Snapshot trước treatment; label churn trong 30 ngày sau quyết định.
- Randomized offer propensity 0.5 và heterogeneous response có cả persuadable lẫn sleeping-dog/do-not-disturb customers.
- Price shock, outage regime và offer fatigue làm outcome drift lẫn treatment-effect drift.
- `true_*` và potential outcomes chỉ nằm trong audit layer; schema test cấm đưa chúng vào model.
- Customer churn sẽ rời risk set ở tháng sau, nên số active customer giảm theo thời gian.

## Không được suy diễn

Các hệ số, tiền tệ và response curve do code đặt ra. Chúng chứng minh pipeline có thể phát hiện risk ≠ persuadability, leakage và drift; chúng không ước lượng Orange, IBM hay bất kỳ telco thật nào.
