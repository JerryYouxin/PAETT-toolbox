#flag:
flag1 = 0
flag2 = 0
flagpapi11 = 0
flagpapi12 = 0
flagpapi21 = 0
flagpapi22 = 0
flagpapi31 = 0
flagpapi32 = 0
flagpapi41 = 0
flagpapi42 = 0
flagpapi51 = 0
flagpapi52 = 0
flagpapi61 = 0
flagpapi62 = 0
flagpapi71 = 0
flagpapi72 = 0


trainSet = open("bt_trainset","w")
#选择region(cnodeid)：
for regCnodeid in [2,15,41,45,49,57]:
	cnodeid = "<row cnodeId=\""+str(regCnodeid)+"\">"
	#cubefile = "22-20.cube"

	for core in [12,13,14,15,16,17,18,19,20,21,22,23,24]:
		for uncore in [12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27]:
		
			cubefile = str(core)+"-"+str(uncore)+".cube"

			f = open(cubefile,'r')

			#init metric	
			br_ntk = 0
			ld_in = 0
			l2_icr = 0
			br_msp = 0
			res_stl = 0
			sr_ins = 0
			l2_dcr = 0
			energy = 0

			for line in f.readlines():

			#PAPI_BR_NTK metric id=8
				if line.find("<matrix metricId=\"8\">")==0:
					flagpapi11 = 1

				if flagpapi11 ==1 and line.startswith(cnodeid):
					flagpapi12 = 1

				if flagpapi11==1 and flagpapi12==1 and line.startswith("("):
					papi_br_ntk = line.replace("(",",")
					papi_br_ntk = papi_br_ntk.replace(")",",")
					papi_br_ntk = papi_br_ntk.replace(":",",")
					papi_br_ntk = papi_br_ntk.replace("-","0")
					papi_br_ntk = papi_br_ntk.split(",")
					br_ntk += (float)(papi_br_ntk[1]) * (float)(papi_br_ntk[5])

				if flagpapi11==1 and flagpapi12==1 and line.startswith("</row>"):
					flagpapi12 = 0

				if line.find("</matrix>")==0:
					flagpapi11 = 0





			#PAPI_LD_IN metric id=9
				if line.find("<matrix metricId=\"9\">")==0:
					flagpapi21 = 1

				if flagpapi21 ==1 and line.startswith(cnodeid):
					flagpapi22 = 1

				if flagpapi21==1 and flagpapi22==1 and line.startswith("("):
					papi_ld_in = line.replace("(",",")
					papi_ld_in = papi_ld_in.replace(")",",")
					papi_ld_in = papi_ld_in.replace(":",",")
					papi_ld_in = papi_ld_in.replace("-","0")
					papi_ld_in = papi_ld_in.split(",")
					ld_in += (float)(papi_ld_in[1]) * (float)(papi_ld_in[5])

				if flagpapi21==1 and flagpapi22==1 and line.startswith("</row>"):
					flagpapi22 = 0

				if line.find("</matrix>")==0:
					flagpapi21 = 0



			#PAPI_L2_ICR metric id=10
				if line.find("<matrix metricId=\"10\">")==0:
					flagpapi31 = 1

				if flagpapi31 ==1 and line.startswith(cnodeid):
					flagpapi32 = 1

				if flagpapi31==1 and flagpapi32==1 and line.startswith("("):
					papi_l2_icr = line.replace("(",",")
					papi_l2_icr = papi_l2_icr.replace(")",",")
					papi_l2_icr = papi_l2_icr.replace(":",",")
					papi_l2_icr = papi_l2_icr.replace("-","0")
					papi_l2_icr = papi_l2_icr.split(",")
					l2_icr += (float)(papi_l2_icr[1]) * (float)(papi_l2_icr[5])

				if flagpapi31==1 and flagpapi32==1 and line.startswith("</row>"):
					flagpapi32 = 0

				if line.find("</matrix>")==0:
					flagpapi31 = 0



			#PAPI_BR_MSP metric id=11
				if line.find("<matrix metricId=\"11\">")==0:
					flagpapi41 = 1

				if flagpapi41 ==1 and line.startswith(cnodeid):
					flagpapi42 = 1

				if flagpapi41==1 and flagpapi42==1 and line.startswith("("):
					papi_br_msp = line.replace("(",",")
					papi_br_msp = papi_br_msp.replace(")",",")
					papi_br_msp = papi_br_msp.replace(":",",")
					papi_br_msp = papi_br_msp.replace("-","0")
					papi_br_msp = papi_br_msp.split(",")
					br_msp += (float)(papi_br_msp[1]) * (float)(papi_br_msp[5])

				if flagpapi41==1 and flagpapi42==1 and line.startswith("</row>"):
					flagpapi42 = 0

				if line.find("</matrix>")==0:
					flagpapi41 = 0


			#PAPI_RES_STL metric id=12
				if line.find("<matrix metricId=\"12\">")==0:
					flagpapi51 = 1

				if flagpapi51 ==1 and line.startswith(cnodeid):
					flagpapi52 = 1

				if flagpapi51==1 and flagpapi52==1 and line.startswith("("):
					papi_res_stl = line.replace("(",",")
					papi_res_stl = papi_res_stl.replace(")",",")
					papi_res_stl = papi_res_stl.replace(":",",")
					papi_res_stl = papi_res_stl.replace("-","0")
					papi_res_stl = papi_res_stl.split(",")
					res_stl += (float)(papi_res_stl[1]) * (float)(papi_res_stl[5])

				if flagpapi51==1 and flagpapi52==1 and line.startswith("</row>"):
					flagpapi52 = 0

				if line.find("</matrix>")==0:
					flagpapi51 = 0


			#PAPI_SR_INS metric id=13
				if line.find("<matrix metricId=\"13\">")==0:
					flagpapi61 = 1

				if flagpapi61 ==1 and line.startswith(cnodeid):
					flagpapi62 = 1

				if flagpapi61==1 and flagpapi62==1 and line.startswith("("):
					papi_sr_ins = line.replace("(",",")
					papi_sr_ins = papi_sr_ins.replace(")",",")
					papi_sr_ins = papi_sr_ins.replace(":",",")
					papi_sr_ins = papi_sr_ins.replace("-","0")
					papi_sr_ins = papi_sr_ins.split(",")
					sr_ins += (float)(papi_sr_ins[1]) * (float)(papi_sr_ins[5])

				if flagpapi61==1 and flagpapi62==1 and line.startswith("</row>"):
					flagpapi62 = 0

				if line.find("</matrix>")==0:
					flagpapi61 = 0


			#PAPI_L2_DCR metric id=14
				if line.find("<matrix metricId=\"14\">")==0:
					flagpapi71 = 1

				if flagpapi71 ==1 and line.startswith(cnodeid):
					flagpapi72 = 1

				if flagpapi71==1 and flagpapi72==1 and line.startswith("("):
					papi_l2_dcr = line.replace("(",",")
					papi_l2_dcr = papi_l2_dcr.replace(")",",")
					papi_l2_dcr = papi_l2_dcr.replace(":",",")
					papi_l2_dcr = papi_l2_dcr.replace("-","0")
					papi_l2_dcr = papi_l2_dcr.split(",")
					l2_dcr += (float)(papi_l2_dcr[1]) * (float)(papi_l2_dcr[5])

				if flagpapi71==1 and flagpapi72==1 and line.startswith("</row>"):
					flagpapi72 = 0

				if line.find("</matrix>")==0:
					flagpapi71 = 0


			#energy
				if line.find("<matrix metricId=\"15\">")==0:
					flag1 = 1

				if flag1==1 and line.startswith(cnodeid):
					flag2 = 1

				if flag1==1 and flag2==1 and line.startswith("("):
					x=line.replace("(",",")
					x=x.replace(")",",")
					x=x.replace(":",",")
					x=x.replace("-","0")
					x = x.split(",")
					energy += (float)(x[1]) * (float)(x[5])

				if flag1==1 and flag2==1 and line.startswith("</row>"):
					flag2 = 0

				if line.find("</severity>")==0:
					flag1 = 0


			f.close()
			trainSenMsg = [core,uncore,br_ntk,br_msp,l2_dcr,l2_icr,sr_ins,ld_in,res_stl,energy]
			trainSet.writelines(str(trainSenMsg))
			trainSet.write("\n")
			#print(core,uncore,br_ntk,br_msp,l2_dcr,l2_icr,sr_ins,ld_in,res_stl,energy)
			print(trainSenMsg)


trainSet.close()
