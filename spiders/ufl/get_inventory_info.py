# -*- coding: utf-8 -*-
# @Time    : 2024/5/23 18:04
# @Description :
from datetime import datetime
from plugins.log import logger

from spiders.ufl.base import UFLBase


class UFLInventory(UFLBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wms_ufl_order_detail_table = "wms_ufl_inventory_detail"
        self.account_list = []

    @staticmethod
    def item_mapping():
        return {
            "userAttr2": "user_attr_2",
            "userAttr3": "user_attr_3",
            "vendorPartDesc": "vendor_part_desc",
            "userAttr1": "user_attr_1",
            "kgPerCarton": "kg_per_carton",
            "soNo": "so_no",
            "lastCheckDtLoc": "last_check_dt_loc",
            "cbmPerCarton": "cbm_per_carton",
            "warehouseCode": "warehouse_code",
            "userAttr4": "user_attr_4",
            "vendorCode": "vendor_code",
            "userAttr5": "user_attr_5",
            "createdServer": "created_server",
            "qtyPerPkg": "qty_per_pkg",
            "poNo": "po_no",
            "noOfPkg": "no_of_pkg",
            "pkgUnit": "pkg_unit",
            "qtyIntent": "qty_intent",
            "manufactureDate": "manufacture_date",
            "revisionNo": "revision_no",
            "lotRnManuNo": "lot_rn_manu_no",
            "invoiceNo": "invoice_no",
            "seqId": "seq_id",
            "rmaNo": "rma_no",
            "expirationDate": "expiration_date",
            "createdDtLoc": "created_dt_loc",
            "vendorPartNo": "vendor_part_no",
            "normVol": "norm_vol",
            "invStatus": "inv_status",
            "siOrderNo": "si_order_no",
            "storeInDtLoc": "store_in_dt_loc",
            "custCode": "cust_code",
            "attrList": "attr_list",
            "partDesc": "part_desc",
            "serialNo": "serial_no",
            "qtyInv": "qty_inv",
            "trackingNo": "tracking_no",
            "skuNo": "sku_no",
            "lastCheckDtGMT": "last_check_dt_gmt",
            "qtyUnit": "qty_unit",
            "variantNo": "variant_no",
            "storeInDtGMT": "store_in_dt_gmt",
            "remarks": "remarks",
            "createdDtGMT": "created_dt_gmt",
            "partNo": "part_no",
            "normWt": "norm_wt"
        }

    def request_inventory_list(self, account, page=1, retry=0):
        if account["region"] == "VN":
            url = "https://service.ufreight.com:8443/yuenanwos/wosedi/ws/apiObtainInventory"
        else:
            url = "https://member.eplusss.com:8445/service/inventory/queryByCriteria"

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://member.eplusss.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://member.eplusss.com/',
            'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'timezone': 'GMT+8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        }
        headers_token = self.redis.get(self.redis_key)
        if not headers_token:
            logger.error("账号登录已过期, 重新登陆中...")
            self.login(account=account)
            return self.request_inventory_list(account=account, page=page, retry=retry + 1)

        headers["authorization"] = f"Bearer {headers_token.decode('utf8')}"
        self.session.headers.clear()
        self.session.headers.update(headers)

        json_data = {
            "warehouseCode": account["warehouseCode"],
            "customer": account["customer"],
            "groupByParams": "partNoGroup,qtyUnit,expirationDate",
            "page": page,
            "pageSize": 10,
        }

        response = self.get_response(url=url, json_data=json_data)
        if not response: return
        if response.status_code == 401:
            if retry < 1:
                logger.error("账号登录已过期, 重新登陆中...")
                self.login(account=account)
                return self.request_inventory_list(account=account, page=page, retry=retry + 1)
            else:
                logger.error(f"账号重新登录达到最大次数, 请手动检查! {response.json()}")

        data = response.json()["data"]
        total_count = data["totalCount"]
        _list = data["PartInvList"]

        logger.info(f"正在抓取ufl库存明细 {account['username']} 第{page}页 当前页{len(_list)}条 共{total_count}条")
        insert_list = []
        for inv in _list:
            mapping = self.item_mapping()
            insert_data = {mapping[k]: v for k, v in inv.items() if k in mapping}
            insert_data["dt"] = datetime.now().strftime('%Y-%m-%d')
            insert_list.append(insert_data)

        self.db.batch_insert_replace(self.wms_ufl_order_detail_table, insert_list, method="replace")

        if page * 10 < total_count:
            return self.request_inventory_list(account=account, page=page + 1)

    def get_order_from_accounts(self):
        for account in self.account_list:
            self.get_account_setting(account=account)
            self.session = self.get_session()
            self.request_inventory_list(account=account)


def wms_ufl_inventory_detail():
    uo = UFLInventory()
    uo.get_order_from_accounts()


if __name__ == '__main__':
    uo = UFLInventory()
    uo.get_order_from_accounts()
